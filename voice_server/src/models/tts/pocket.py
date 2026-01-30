"""Pocket TTS model implementation.

Integrates the external pocket-tts package with thread-safe worker pattern.
Pocket TTS is CPU-only and NOT thread-safe, so we use a single worker
with asyncio queues for concurrent session handling.
"""

import asyncio
from pathlib import Path
from typing import Optional, AsyncIterator

import numpy as np

from voice_server.config.logging_config import get_logger
from voice_server.src.models.tts.base import (
    TTSModelBase,
    TTSConfig,
    TTSModelName,
    TTSResult,
    TTSChunk,
)
from voice_server.src.core.exceptions import ModelException
from voice_server.src.models.tts.worker import TTSWorker

logger = get_logger(__name__)


class PocketTTSModel(TTSModelBase):
    """Pocket TTS model implementation.

    Pocket TTS is a CPU-only, 100M parameter TTS model that is NOT
    thread-safe. This implementation uses a single worker pattern
    with asyncio queues to handle multiple concurrent sessions.
    """

    def __init__(self, config: TTSConfig):
        """Initialize the Pocket TTS model.

        Args:
            config: TTS configuration.
        """
        super().__init__(config)
        self._worker: Optional[TTSWorker] = None
        self._voices_path: Optional[Path] = None

    async def initialize(self) -> None:
        """Initialize the model and start the worker.

        Raises:
            ModelException: If initialization fails.
        """
        if self._initialized:
            return

        try:
            logger.info("Initializing Pocket TTS model...")

            # Import pocket-tts
            try:
                from pocket_tts import TTSModel

                self._TTSModel = TTSModel
            except ImportError as e:
                raise ModelException(
                    "pocket-tts package not installed. "
                    "Install it with: pip install pocket-tts"
                ) from e

            # Create and start worker
            self._worker = TTSWorker(self._TTSModel)
            await self._worker.start()

            self._initialized = True
            logger.info("Pocket TTS model initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Pocket TTS model: {e}")
            raise ModelException(f"Failed to initialize TTS model: {e}") from e

    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize speech from text (non-streaming).

        Args:
            text: Text to synthesize.
            voice_id: Optional voice identifier.

        Returns:
            TTSResult with synthesized audio.

        Raises:
            ModelException: If synthesis fails.
        """
        if not self._initialized:
            raise RuntimeError("Model not initialized")

        voice_id = voice_id or self.config.voice_id

        try:
            # Submit synthesis request to worker
            audio_chunks = []
            total_duration = 0.0

            async for chunk in self._worker.synthesize(
                text=text,
                voice_id=voice_id,
                speed=self.config.speed,
                stability=self.config.stability,
                pitch=self.config.pitch,
            ):
                audio_chunks.append(chunk.audio)
                total_duration += chunk.duration if hasattr(chunk, "duration") else 0.0

            # Combine chunks
            combined_audio = b"".join(audio_chunks)

            # Convert to output format if needed
            output_audio = await self._convert_output_format(combined_audio)

            return TTSResult(
                audio=output_audio,
                format=self.config.output_format,
                sample_rate=self.config.sample_rate,
                duration=total_duration,
                text=text,
            )

        except Exception as e:
            logger.error(f"Failed to synthesize speech: {e}")
            raise ModelException(f"Failed to synthesize speech: {e}") from e

    async def synthesize_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
    ) -> AsyncIterator[TTSChunk]:
        """Synthesize speech from text with streaming output.

        Args:
            text: Text to synthesize.
            voice_id: Optional voice identifier.

        Yields:
            TTSChunk with audio chunks.
        """
        if not self._initialized:
            raise RuntimeError("Model not initialized")

        voice_id = voice_id or self.config.voice_id
        text_offset = 0

        try:
            async for chunk in self._worker.synthesize(
                text=text,
                voice_id=voice_id,
                speed=self.config.speed,
                stability=self.config.stability,
                pitch=self.config.pitch,
            ):
                # Convert to output format
                output_audio = await self._convert_output_format(chunk.audio)

                yield TTSChunk(
                    audio=output_audio,
                    format=self.config.output_format,
                    sample_rate=self.config.sample_rate,
                    is_final=chunk.is_final,
                    text_offset=text_offset,
                )

                text_offset += len(chunk.text) if getattr(chunk, "text", None) else 0

        except Exception as e:
            logger.error(f"Failed to synthesize speech stream: {e}")
            raise ModelException(f"Failed to synthesize speech: {e}") from e

    async def _convert_output_format(self, audio: bytes) -> bytes:
        """Convert audio to configured output format.

        Args:
            audio: Input audio bytes (assumed PCM int16).

        Returns:
            Audio in output format.
        """
        if self.config.output_format == "pcm_int16":
            return audio
        elif self.config.output_format == "pcm_float32":
            # Convert int16 to float32
            audio_array = np.frombuffer(audio, dtype=np.int16)
            float_array = audio_array.astype(np.float32) / 32768.0
            return float_array.tobytes()
        elif self.config.output_format == "wav":
            # Add WAV header
            from voice_server.src.utils.audio import add_wav_header

            return add_wav_header(audio, self.config.sample_rate, channels=1)
        else:
            raise ValueError(f"Unknown output format: {self.config.output_format}")

    async def list_voices(self) -> list[dict]:
        """List available voices.

        Returns:
            List of voice information dictionaries.
        """
        voices = [
            {
                "voice_id": "default",
                "name": "Default Voice",
                "description": "Built-in default voice",
                "language": "en",
            }
        ]

        # Add custom voices if voices_path is set
        if self._voices_path and self._voices_path.exists():
            for voice_file in self._voices_path.glob("*.safetensors"):
                voice_id = voice_file.stem
                voices.append({
                    "voice_id": voice_id,
                    "name": voice_id,
                    "description": f"Custom voice: {voice_id}",
                    "language": "unknown",
                    "path": str(voice_file),
                })

        return voices

    async def load_voice(self, voice_path: str) -> str:
        """Load a custom voice from file.

        Args:
            voice_path: Path to voice file (.safetensors).

        Returns:
            Voice ID for the loaded voice.

        Raises:
            ModelException: If voice loading fails.
        """
        if not self._initialized:
            raise RuntimeError("Model not initialized")

        try:
            path = Path(voice_path)
            if not path.exists():
                raise ModelException(f"Voice file not found: {voice_path}")

            voice_id = path.stem

            # Load voice via worker
            await self._worker.load_voice(str(path))

            logger.info(f"Loaded custom voice: {voice_id}")
            return voice_id

        except Exception as e:
            logger.error(f"Failed to load voice: {e}")
            raise ModelException(f"Failed to load voice: {e}") from e

    async def switch_voice(self, voice_id: str) -> None:
        """Switch to a different voice.

        Args:
            voice_id: Voice identifier to switch to.

        Raises:
            ModelException: If voice not found.
        """
        if not self._initialized:
            raise RuntimeError("Model not initialized")

        # Update config
        self.config.voice_id = voice_id

        logger.info(f"Switched to voice: {voice_id}")

    def set_voices_path(self, path: str) -> None:
        """Set the path for custom voice files.

        Args:
            path: Directory path for voice files.
        """
        self._voices_path = Path(path)
        logger.info(f"Voices path set to: {path}")

    def get_model_info(self) -> dict:
        """Get information about the current model.

        Returns:
            Dictionary with model information.
        """
        return {
            "model_name": self.config.model_name.value,
            "device": self.config.device,
            "is_initialized": self._initialized,
            "voice_id": self.config.voice_id,
            "voices_path": str(self._voices_path) if self._voices_path else None,
            "worker_active": self._worker.is_running if self._worker else False,
            "output_format": self.config.output_format,
            "sample_rate": self.config.sample_rate,
            "speed": self.config.speed,
            "stability": self.config.stability,
            "pitch": self.config.pitch,
        }

    async def shutdown(self) -> None:
        """Shutdown the model and worker."""
        if self._worker:
            await self._worker.stop()
            self._worker = None

        self._initialized = False
        logger.info("Pocket TTS model shutdown complete")
