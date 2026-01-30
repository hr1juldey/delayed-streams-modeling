"""DEPRECATED: Kyutai STT model implementation.

This module has been deprecated due to CUDA 13.0 compatibility issues.
The moshi library (v0.2.12) causes "Invalid handle" cuBLAS errors on CUDA 13.0.

This implementation has been replaced by whisper.py which uses faster-whisper.
The new implementation provides:
- Better CUDA compatibility (works with CUDA 13.0)
- Multiple model sizes (tiny, base, small, medium, large-v2, large-v3)
- Multilingual support
- Active maintenance

This file is kept for reference only. Use WhisperSTTModel instead.

Replacement: voice_server.src.models.stt.whisper.WhisperSTTModel
Deprecated: 2025-01-30
"""

import asyncio
import itertools
import math
import time
import threading
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import torch
import moshi.models
import julius
import sphn

from voice_server.config.logging_config import get_logger
from voice_server.src.models.stt.base import (
    STTModelBase,
    STTConfig,
    STTModelName,
    STTResult,
    STTSegment,
)
from voice_server.src.core.exceptions import ModelException

logger = get_logger(__name__)


# Data structure for timestamped text (from stt_from_file_pytorch.py)
class TimestampedText:
    """Text with timestamp information."""

    def __init__(self, text: str, timestamp: tuple[float, float]):
        self.text = text
        self.timestamp = timestamp

    def __str__(self):
        return f"{self.text} ({self.timestamp[0]:.2f}:{self.timestamp[1]:.2f})"

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "text": self.text,
            "start_time": self.timestamp[0],
            "end_time": self.timestamp[1],
        }


class SessionState:
    """State for an active STT streaming session."""

    def __init__(
        self,
        session_id: str,
        mimi_frame_rate: int,
        tokenizer,
        silence_prefix_chunks: int,
        delay_chunks: int,
        mimi_frame_size: int,
    ):
        self.session_id = session_id
        self.mimi_frame_rate = mimi_frame_rate
        self.tokenizer = tokenizer
        self.silence_prefix_chunks = silence_prefix_chunks
        self.delay_chunks = delay_chunks
        self.mimi_frame_size = mimi_frame_size

        # State
        self.text_tokens_accum = []
        self.chunk_count = 0
        self.start_time = time.time()
        self.last_vad_state = False
        self.accumulated_text = ""
        self.last_result_time = 0.0

        # For partial results
        self.partial_tokens = []
        self.partial_text = ""

    def add_tokens(self, tokens: torch.Tensor) -> Optional[str]:
        """Add text tokens and return any new text."""
        text_token = tokens[0, 0, 0].cpu().item()

        # Skip padding and special tokens
        if text_token in (0, 3):
            return None

        # Decode token
        _text = self.tokenizer.id_to_piece(text_token)
        _text = _text.replace("▁", " ")

        # Update accumulated text
        self.accumulated_text += _text
        self.partial_tokens.append(text_token)
        self.partial_text = self.accumulated_text

        return _text

    def get_partial_result(self) -> str:
        """Get current partial result."""
        return self.partial_text

    def get_final_result(self) -> str:
        """Get final accumulated result."""
        return self.accumulated_text

    def reset_partial(self) -> None:
        """Reset partial text (after final result)."""
        self.partial_text = ""
        self.partial_tokens = []


class KyutaiSTTModel(STTModelBase):
    """Kyutai STT model implementation.

    Supports both 1B-en_fr and 2.6B-en models with streaming inference.
    """

    def __init__(self, config: STTConfig):
        """Initialize the Kyutai STT model.

        Args:
            config: STT configuration.
        """
        super().__init__(config)
        self.device = config.device
        self.model_name = config.model_name

        # Model components (loaded during initialize)
        self.checkpoint_info = None
        self.mimi = None
        self.tokenizer = None
        self.lm = None
        self.lm_gen = None

        # Configuration
        self.audio_silence_prefix_seconds = 1.0
        self.audio_delay_seconds = 5.0
        self.padding_token_id = 3

        # Session management
        self._sessions: dict[str, SessionState] = {}
        self._sessions_lock = asyncio.Lock()

        # Single-threaded executor for CUDA operations
        # All CUDA operations must run in the same thread to maintain CUDA context
        self._executor: Optional[ThreadPoolExecutor] = None

    async def initialize(self) -> None:
        """Initialize the model and load weights."""
        if self._initialized:
            return

        try:
            logger.info(f"Loading Kyutai STT model: {self.model_name.value}")

            # Create single-threaded executor for CUDA operations
            # All CUDA operations must run in the same thread
            loop = asyncio.get_event_loop()
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stt_cuda_")

            # Determine repo name
            if self.model_name == STTModelName.EN_FR_1B:
                hf_repo = "kyutai/stt-1b-en_fr-candle"
            elif self.model_name == STTModelName.EN_2_6B:
                hf_repo = "kyutai/stt-2.6b-en-candle"
            else:
                raise ValueError(f"Unknown model: {self.model_name}")

            # Load checkpoint info from HuggingFace (using dedicated executor)
            self.checkpoint_info = await loop.run_in_executor(
                self._executor,
                self._load_checkpoint_info_with_cuda,
                hf_repo,
            )

            # Get STT configuration
            self.audio_silence_prefix_seconds = self.checkpoint_info.stt_config.get(
                "audio_silence_prefix_seconds", 1.0
            )
            self.audio_delay_seconds = self.checkpoint_info.stt_config.get(
                "audio_delay_seconds", 5.0
            )
            self.padding_token_id = self.checkpoint_info.raw_config.get(
                "text_padding_token_id", 3
            )

            # Load Mimi encoder (using dedicated executor)
            self.mimi = await loop.run_in_executor(
                self._executor,
                self._load_mimi_with_cuda,
            )

            # Load tokenizer
            self.tokenizer = self.checkpoint_info.get_text_tokenizer()

            # Load LM model (using dedicated executor)
            self.lm = await loop.run_in_executor(
                self._executor,
                self._load_moshi_with_cuda,
            )

            # Create LM generator in executor thread to ensure CUDA context
            self.lm_gen = await loop.run_in_executor(
                self._executor,
                self._create_lm_gen,
            )

            self._initialized = True
            logger.info(
                f"Kyutai STT model loaded successfully: {self.model_name.value} on {self.device}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Kyutai STT model: {e}")
            raise ModelException(f"Failed to initialize STT model: {e}") from e

    def _load_checkpoint_info_with_cuda(self, hf_repo: str):
        """Load checkpoint info with CUDA context set."""
        if self.device.startswith("cuda"):
            # Extract device index (e.g., "cuda" -> 0, "cuda:1" -> 1)
            if ":" in self.device:
                device_idx = int(self.device.split(":")[1])
            else:
                device_idx = 0
            torch.cuda.set_device(device_idx)
        return moshi.models.loaders.CheckpointInfo.from_hf_repo(hf_repo)

    def _load_mimi_with_cuda(self):
        """Load Mimi encoder with CUDA context set."""
        if self.device.startswith("cuda"):
            if ":" in self.device:
                device_idx = int(self.device.split(":")[1])
            else:
                device_idx = 0
            torch.cuda.set_device(device_idx)
        return self.checkpoint_info.get_mimi(device=self.device)

    def _load_moshi_with_cuda(self):
        """Load Moshi LM with CUDA context set."""
        if self.device.startswith("cuda"):
            if ":" in self.device:
                device_idx = int(self.device.split(":")[1])
            else:
                device_idx = 0
            torch.cuda.set_device(device_idx)
        return self.checkpoint_info.get_moshi(device=self.device, dtype=torch.bfloat16)

    def _create_lm_gen(self):
        """Create LM generator with CUDA context set."""
        if self.device.startswith("cuda"):
            if ":" in self.device:
                device_idx = int(self.device.split(":")[1])
            else:
                device_idx = 0
            torch.cuda.set_device(device_idx)
        return moshi.models.LMGen(self.lm, temp=0, temp_text=0.0)

    async def start_stream(self, session_id: str) -> None:
        """Start a new streaming session."""
        if not self._initialized:
            raise RuntimeError("Model not initialized")

        async with self._sessions_lock:
            if session_id in self._sessions:
                logger.warning(f"Session already exists: {session_id}")
                return

            # Create session state
            n_prefix_chunks = math.ceil(
                self.audio_silence_prefix_seconds * self.mimi.frame_rate
            )
            n_delay_chunks = math.ceil(self.audio_delay_seconds * self.mimi.frame_rate)

            session = SessionState(
                session_id=session_id,
                mimi_frame_rate=self.mimi.frame_rate,
                tokenizer=self.tokenizer,
                silence_prefix_chunks=n_prefix_chunks,
                delay_chunks=n_delay_chunks,
                mimi_frame_size=self.mimi.frame_size,
            )

            self._sessions[session_id] = session
            self._streaming_active = True

            logger.info(f"Started STT stream for session: {session_id}")

    async def process_audio_chunk(
        self,
        audio: np.ndarray,
        session_id: str,
    ) -> Optional[STTResult]:
        """Process an audio chunk in streaming mode."""
        if not self._initialized:
            raise RuntimeError("Model not initialized")

        session = self._sessions.get(session_id)
        if session is None:
            raise RuntimeError(f"No active session for: {session_id}")

        try:
            # Run CUDA operations in dedicated executor to maintain consistent CUDA context
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._executor,
                self._process_audio_chunk_sync,
                audio,
                session,
            )
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            raise ModelException(f"Failed to process audio: {e}") from e

    def _process_audio_chunk_sync(
        self,
        audio: np.ndarray,
        session: SessionState,
    ) -> Optional[STTResult]:
        """Synchronous audio processing - must run in thread pool for CUDA consistency."""
        # Ensure CUDA context is properly set in this thread
        if self.device.startswith("cuda"):
            if ":" in self.device:
                device_idx = int(self.device.split(":")[1])
            else:
                device_idx = 0
            torch.cuda.set_device(device_idx)

        # Convert to torch tensor
        audio_tensor = torch.from_numpy(audio).to(self.device)

        # Resample if needed
        if audio_tensor.shape[-1] % self.mimi.frame_size != 0:
            to_pad = self.mimi.frame_size - audio_tensor.shape[-1] % self.mimi.frame_size
            audio_tensor = torch.nn.functional.pad(audio_tensor, (0, to_pad))

        # Create silence chunk for padding
        silence_chunk = torch.zeros(
            (1, 1, self.mimi.frame_size),
            dtype=torch.float32,
            device=self.device,
        )

        # Process in streaming context
        with self.mimi.streaming(1), self.lm_gen.streaming(1):
            # Add silence prefix on first chunk
            if session.chunk_count == 0:
                for _ in range(session.silence_prefix_chunks):
                    audio_tokens = self.mimi.encode(silence_chunk)
                    if self.config.vad_mode == "server":
                        text_tokens, vad_heads = self.lm_gen.step_with_extra_heads(
                            audio_tokens
                        )
                    else:
                        text_tokens = self.lm_gen.step(audio_tokens)

            # Process actual audio
            # Reshape to [batch, channels, time] for mimi encoder
            audio_tensor = audio_tensor[None, None, :]  # [1, 1, time]
            for audio_chunk in torch.split(
                audio_tensor, self.mimi.frame_size, dim=-1
            ):
                session.chunk_count += 1

                # Encode audio
                audio_tokens = self.mimi.encode(audio_chunk)

                # Step LM
                if self.config.vad_mode == "server":
                    text_tokens, vad_heads = self.lm_gen.step_with_extra_heads(
                        audio_tokens
                    )

                    # Check VAD
                    if vad_heads:
                        pr_vad = vad_heads[2][0, 0, 0].cpu().item()
                        if pr_vad > 0.5:
                            # End of speech detected
                            logger.debug(f"VAD detected end of speech: {session.session_id}")
                            # Return final result
                            final_text = session.get_final_result()
                            session.reset_partial()
                            return STTResult(
                                text=final_text,
                                is_partial=False,
                                is_final=True,
                                confidence=0.9,  # VAD confidence
                                timestamp_start=0.0,
                                timestamp_end=time.time() - session.start_time,
                            )
                else:
                    text_tokens = self.lm_gen.step(audio_tokens)

                # Accumulate tokens
                session.text_tokens_accum.append(text_tokens)

                # Get new text
                new_text = session.add_tokens(text_tokens)

                # Determine if we should return a result
                now = time.time()
                time_since_last = now - session.last_result_time
                should_return = False

                if self.config.streaming_mode in ("partial", "both"):
                    # Return partial result periodically
                    if new_text and time_since_last > 0.1:  # Max 10 partial per second
                        should_return = True

                if should_return:
                    session.last_result_time = now
                    return STTResult(
                        text=session.get_partial_result(),
                        is_partial=True,
                        is_final=False,
                        confidence=0.7,  # Partial result confidence
                        timestamp_start=0.0,
                        timestamp_end=time.time() - session.start_time,
                    )

        return None

    async def finalize_stream(self, session_id: str) -> STTResult:
        """Finalize a streaming session and get final result."""
        session = self._sessions.get(session_id)
        if session is None:
            raise RuntimeError(f"No active session for: {session_id}")

        try:
            # Run CUDA operations in dedicated executor to maintain consistent CUDA context
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._executor,
                self._finalize_stream_sync,
                session,
            )
        except Exception as e:
            logger.error(f"Error finalizing stream: {e}")
            raise ModelException(f"Failed to finalize stream: {e}") from e

    def _finalize_stream_sync(self, session: SessionState) -> STTResult:
        """Synchronous stream finalization - must run in thread pool for CUDA consistency."""
        # Ensure CUDA context is properly set in this thread
        if self.device.startswith("cuda"):
            if ":" in self.device:
                device_idx = int(self.device.split(":")[1])
            else:
                device_idx = 0
            torch.cuda.set_device(device_idx)

        # Add delay suffix chunks
        silence_chunk = torch.zeros(
            (1, 1, self.mimi.frame_size),
            dtype=torch.float32,
            device=self.device,
        )

        with self.mimi.streaming(1), self.lm_gen.streaming(1):
            for _ in range(session.delay_chunks):
                audio_tokens = self.mimi.encode(silence_chunk)
                if self.config.vad_mode == "server":
                    text_tokens, vad_heads = self.lm_gen.step_with_extra_heads(
                        audio_tokens
                    )
                else:
                    text_tokens = self.lm_gen.step(audio_tokens)
                session.text_tokens_accum.append(text_tokens)
                session.add_tokens(text_tokens)

        # Get final text
        final_text = session.get_final_result()
        duration = time.time() - session.start_time

        return STTResult(
            text=final_text,
            is_partial=False,
            is_final=True,
            confidence=0.9,
            timestamp_start=0.0,
            timestamp_end=duration,
        )

    async def end_stream(self, session_id: str) -> None:
        """End a streaming session."""
        async with self._sessions_lock:
            if session_id in self._sessions:
                del self._sessions[session_id]

            if not self._sessions:
                self._streaming_active = False

            logger.info(f"Ended STT stream for session: {session_id}")

    async def transcribe(self, audio: np.ndarray) -> STTSegment:
        """Transcribe a complete audio file (non-streaming)."""
        if not self._initialized:
            raise RuntimeError("Model not initialized")

        try:
            # Run CUDA operations in dedicated executor to maintain consistent CUDA context
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._transcribe_sync,
                audio,
            )
            return result
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise ModelException(f"Failed to transcribe audio: {e}") from e

    def _transcribe_sync(self, audio: np.ndarray) -> STTSegment:
        """Synchronous transcription - must run in thread pool for CUDA consistency."""
        # Ensure CUDA context is properly set in this thread
        if self.device.startswith("cuda"):
            if ":" in self.device:
                device_idx = int(self.device.split(":")[1])
            else:
                device_idx = 0
            torch.cuda.set_device(device_idx)

        # Use the full transcription logic from stt_from_file_pytorch.py
        # This is a simplified version - full version would include timestamps

        audio_tensor = torch.from_numpy(audio).to(self.device)
        audio_tensor = julius.resample_frac(
            audio_tensor, 24000, self.mimi.sample_rate
        )

        # Pad to frame size
        if audio_tensor.shape[-1] % self.mimi.frame_size != 0:
            to_pad = self.mimi.frame_size - audio_tensor.shape[-1] % self.mimi.frame_size
            audio_tensor = torch.nn.functional.pad(audio_tensor, (0, to_pad))

        # Process all chunks
        text_tokens_accum = []
        n_prefix_chunks = math.ceil(
            self.audio_silence_prefix_seconds * self.mimi.frame_rate
        )
        n_delay_chunks = math.ceil(self.audio_delay_seconds * self.mimi.frame_rate)

        silence_chunk = torch.zeros(
            (1, 1, self.mimi.frame_size), dtype=torch.float32, device=self.device
        )

        chunks = itertools.chain(
            itertools.repeat(silence_chunk, n_prefix_chunks),
            torch.split(audio_tensor[:, None], self.mimi.frame_size, dim=-1),
            itertools.repeat(silence_chunk, n_delay_chunks),
        )

        start_time = time.time()
        with self.mimi.streaming(1), self.lm_gen.streaming(1):
            for audio_chunk in chunks:
                audio_tokens = self.mimi.encode(audio_chunk)
                text_tokens = self.lm_gen.step(audio_tokens)
                text_tokens_accum.append(text_tokens)

        duration = time.time() - start_time

        # Decode tokens to text
        utterance_tokens = torch.concat(text_tokens_accum, dim=-1)

        # Extract timestamped words (this is already thread-safe, runs inline)
        words = self._extract_timestamped_words_sync(
            utterance_tokens,
            n_prefix_chunks,
        )

        # Combine words into full text
        full_text = " ".join([w["text"] for w in words])

        return STTSegment(
            text=full_text,
            words=words,
            start_time=0.0,
            end_time=duration,
            confidence=0.9,
        )

    async def _extract_timestamped_words(
        self,
        text_tokens: torch.Tensor,
        n_prefix_chunks: int,
    ) -> list[dict]:
        """Extract timestamped words from text tokens.

        Implements the logic from stt_from_file_pytorch.py tokens_to_timestamped_text.
        """
        # Run in thread pool to avoid blocking
        return await asyncio.to_thread(
            self._extract_timestamped_words_sync,
            text_tokens,
            n_prefix_chunks,
        )

    def _extract_timestamped_words_sync(
        self,
        text_tokens: torch.Tensor,
        n_prefix_chunks: int,
    ) -> list[dict]:
        """Synchronous version of timestamp extraction."""
        words = []
        text_tokens = text_tokens.cpu().view(-1)

        def _tstmp(start_position, end_position):
            offset_seconds = n_prefix_chunks / self.mimi.frame_rate + self.audio_delay_seconds
            return (
                max(0, start_position / self.mimi.frame_rate - offset_seconds),
                max(0, end_position / self.mimi.frame_rate - offset_seconds),
            )

        def _decode(t):
            t = t[t > self.padding_token_id]
            return self.tokenizer.decode(t.numpy().tolist())

        def _decode_segment(start, end):
            nonlocal words

            text = _decode(text_tokens[start:end])
            words_inside_segment = text.split()

            if len(words_inside_segment) == 0:
                return
            if len(words_inside_segment) == 1:
                words.append(
                    {
                        "text": text,
                        "start_time": _tstmp(start, end)[0],
                        "end_time": _tstmp(start, end)[1],
                    }
                )
            else:
                # Multiple words without boundary
                for adjacent_word in words_inside_segment[:-1]:
                    n_tokens = len(self.tokenizer.encode(adjacent_word))
                    words.append(
                        {
                            "text": adjacent_word,
                            "start_time": _tstmp(start, start + n_tokens)[0],
                            "end_time": _tstmp(start, start + n_tokens)[1],
                        }
                    )
                    start += n_tokens

                adjacent_word = words_inside_segment[-1]
                words.append(
                    {
                        "text": adjacent_word,
                        "start_time": _tstmp(start, end)[0],
                        "end_time": _tstmp(start, end)[1],
                    }
                )

        (segment_boundaries,) = torch.where(text_tokens == 0)  # end_of_padding_id

        if not segment_boundaries.numel():
            return []

        for i in range(len(segment_boundaries) - 1):
            segment_start = int(segment_boundaries[i]) + 1
            segment_end = int(segment_boundaries[i + 1])
            _decode_segment(segment_start, segment_end)

        # Handle last segment
        last_segment_start = segment_boundaries[-1] + 1
        boundary_token = torch.tensor([self.tokenizer.eos_id()])
        (end_of_last_segment,) = torch.where(
            torch.isin(text_tokens[last_segment_start:], boundary_token)
        )

        if not end_of_last_segment.numel():
            last_segment_end = min(
                text_tokens.shape[-1], last_segment_start + self.mimi.frame_rate
            )
        else:
            last_segment_end = last_segment_start + end_of_last_segment[0]

        _decode_segment(last_segment_start, last_segment_end)

        return words

    async def switch_model(self, new_model_name: STTModelName) -> None:
        """Switch to a different model variant."""
        if self._sessions:
            raise RuntimeError("Cannot switch model with active sessions")

        logger.info(f"Switching STT model from {self.model_name} to {new_model_name}")

        # Shutdown old executor and unload current model
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

        self.checkpoint_info = None
        self.mimi = None
        self.tokenizer = None
        self.lm = None
        self.lm_gen = None
        self._initialized = False

        # Update config and reload
        self.model_name = new_model_name
        await self.initialize()

    def get_model_info(self) -> dict:
        """Get information about the current model."""
        return {
            "model_name": self.model_name.value,
            "device": self.device,
            "sample_rate": self.mimi.sample_rate if self.mimi else 24000,
            "frame_rate": self.mimi.frame_rate if self.mimi else 0,
            "frame_size": self.mimi.frame_size if self.mimi else 0,
            "is_initialized": self._initialized,
            "active_sessions": len(self._sessions),
            "audio_silence_prefix_seconds": self.audio_silence_prefix_seconds,
            "audio_delay_seconds": self.audio_delay_seconds,
        }

    @property
    def active_session_count(self) -> int:
        """Get number of active streaming sessions."""
        return len(self._sessions)

    def get_active_sessions(self) -> set[str]:
        """Get set of active session IDs."""
        return set(self._sessions.keys())

    async def shutdown(self) -> None:
        """Shutdown the model and cleanup resources.

        Properly closes the executor and clears model references.
        """
        logger.info("Shutting down Kyutai STT model...")

        # Close all sessions
        self._sessions.clear()

        # Shutdown executor
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

        # Clear model references to free memory
        self.checkpoint_info = None
        self.mimi = None
        self.tokenizer = None
        self.lm = None
        self.lm_gen = None

        self._initialized = False
        logger.info("Kyutai STT model shutdown complete")
