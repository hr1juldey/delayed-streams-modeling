"""Whisper STT model using faster-whisper."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import numpy as np

from voice_server.config.logging_config import get_logger
from voice_server.src.models.stt.base import (
    STTConfig,
    STTModelBase,
    STTModelName,
    STTResult,
    STTSegment,
)
from voice_server.src.utils.audio import resample

logger = get_logger(__name__)

# Whisper models are trained on 16kHz audio
WHISPER_SAMPLE_RATE = 16000


@dataclass
class SessionState:
    """Streaming session state for Whisper STT."""

    audio_buffer: list[np.ndarray] = field(default_factory=list)
    total_samples: int = 0
    input_sample_rate: int = 16000  # Frontend now sends 16kHz PCM directly


class WhisperSTTModel(STTModelBase):
    """Whisper STT model using faster-whisper (CTranslate2).

    Features:
    - Better CUDA compatibility than moshi
    - Multiple model sizes (tiny to large-v3)
    - Multilingual support
    - Faster inference than openai-whisper
    """

    def __init__(self, config: STTConfig):
        self.config = config
        self._model: object | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._sessions: dict[str, SessionState] = {}
        self._initialized = False
        self._streaming_active = False

    async def initialize(self) -> None:
        """Initialize the Whisper model."""
        loop = asyncio.get_event_loop()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper_")

        self._model = await loop.run_in_executor(
            self._executor,
            self._load_model,
        )

        self._initialized = True
        logger.info(f"Whisper STT model initialized: {self.config.model_name}")

    def _load_model(self) -> object:
        """Load Whisper model (runs in executor thread)."""
        from faster_whisper import WhisperModel

        return WhisperModel(
            self.config.model_name,
            device=self.config.device,
            compute_type=self.config.compute_type or "float16",
        )

    async def start_stream(self, session_id: str) -> None:
        """Start a new streaming session."""
        if not self._initialized:
            raise RuntimeError("Whisper STT model not initialized")

        self._sessions[session_id] = SessionState()
        self._streaming_active = True
        logger.debug(f"Started Whisper stream: {session_id}")

    async def process_audio_chunk(
        self,
        audio: np.ndarray,
        session_id: str,
    ) -> STTResult | None:
        """Process audio chunk for streaming session."""
        if not self._initialized:
            raise RuntimeError("Whisper STT model not initialized")

        session = self._sessions.get(session_id)
        if not session:
            raise RuntimeError(f"Session not found: {session_id}")

        session.audio_buffer.append(audio)
        session.total_samples += len(audio)

        return None

    async def finalize_stream(self, session_id: str) -> STTResult:
        """Finalize stream and get transcription."""
        if not self._initialized:
            raise RuntimeError("Whisper STT model not initialized")

        session = self._sessions.get(session_id)
        if not session:
            raise RuntimeError(f"Session not found: {session_id}")

        audio_data = np.concatenate(session.audio_buffer)

        # Resample from input sample rate to Whisper's 16kHz if needed
        if session.input_sample_rate != WHISPER_SAMPLE_RATE:
            logger.debug(
                f"Resampling audio from {session.input_sample_rate}Hz to {WHISPER_SAMPLE_RATE}Hz"
            )
            loop = asyncio.get_event_loop()
            audio_data = await loop.run_in_executor(
                self._executor,
                resample,
                audio_data,
                session.input_sample_rate,
                WHISPER_SAMPLE_RATE,
            )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor,
            self._transcribe_sync,
            audio_data,
        )

        return STTResult(
            text=result["text"],
            is_partial=False,
            is_final=True,
            confidence=result.get("avg_logprob", 0.0),
            timestamp_start=0.0,
            timestamp_end=len(audio_data) / WHISPER_SAMPLE_RATE,
            tokens=None,
        )

    def _transcribe_sync(self, audio: np.ndarray) -> dict:
        """Synchronous transcription (runs in executor)."""
        segments, info = self._model.transcribe(
            audio,
            language=self.config.language,
            beam_size=5,
            vad_filter=False,  # Disabled - VAD was too aggressive and filtering out all audio
        )

        full_text = " ".join(seg.text for seg in segments).strip()
        avg_logprob = info.language_probability

        return {"text": full_text, "avg_logprob": avg_logprob}

    async def end_stream(self, session_id: str) -> None:
        """End streaming session."""
        self._sessions.pop(session_id, None)
        if not self._sessions:
            self._streaming_active = False
        logger.debug(f"Ended Whisper stream: {session_id}")

    async def transcribe(self, audio: np.ndarray) -> STTSegment:
        """Transcribe complete audio file."""
        if not self._initialized:
            raise RuntimeError("Whisper STT model not initialized")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor,
            self._transcribe_with_timestamps_sync,
            audio,
        )

        return result

    def _transcribe_with_timestamps_sync(self, audio: np.ndarray) -> STTSegment:
        """Transcribe with word timestamps."""
        segments, info = self._model.transcribe(
            audio,
            language=self.config.language,
            beam_size=5,
            word_timestamps=True,
        )

        words = []
        full_text = []
        for seg in segments:
            full_text.append(seg.text)
            for word in seg.words:
                words.append({"word": word.word, "start": word.start, "end": word.end})

        return STTSegment(
            text="".join(full_text).strip(),
            words=words,
            start_time=0.0,
            end_time=len(audio) / WHISPER_SAMPLE_RATE,
            confidence=info.language_probability,
        )

    async def switch_model(self, new_model_name: STTModelName) -> None:
        """Switch to different Whisper model."""
        if self._sessions:
            raise RuntimeError("Cannot switch with active sessions")

        self.config.model_name = new_model_name
        await self.shutdown()
        await self.initialize()

    def get_model_info(self) -> dict:
        """Get model information."""
        return {
            "is_initialized": self._initialized,
            "model_name": self.config.model_name,
            "device": self.config.device,
            "model_type": "whisper",
            "active_sessions": list(self._sessions.keys()),
        }

    async def shutdown(self) -> None:
        """Shutdown model and cleanup."""
        logger.info("Shutting down Whisper STT model...")
        self._sessions.clear()
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
        self._model = None
        self._initialized = False
        logger.info("Whisper STT model shutdown complete")
