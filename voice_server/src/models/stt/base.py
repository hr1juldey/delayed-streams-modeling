"""Base interface for Speech-to-Text models.

Defines the abstract interface that all STT model implementations must follow.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, AsyncIterator
from enum import Enum

import numpy as np


class STTModelName(str, Enum):
    """Available STT model names."""

    EN_FR_1B = "1b-en_fr"
    EN_2_6B = "2.6b-en"


@dataclass
class STTConfig:
    """Configuration for STT model.

    Attributes:
        model_name: Name of the model to use.
        device: Device to run on (cuda, cpu).
        vad_mode: VAD mode (client, server).
        streaming_mode: Streaming output mode (partial, final, both).
        confidence_threshold: Minimum confidence for results.
        target_latency_ms: Target latency in milliseconds.
        custom_vocabulary: Optional custom vocabulary/phrases.
    """

    model_name: STTModelName
    device: str = "cuda"
    vad_mode: str = "client"
    streaming_mode: str = "both"
    confidence_threshold: float = 0.5
    target_latency_ms: int = 200
    custom_vocabulary: Optional[list[str]] = None


@dataclass
class STTResult:
    """Result from STT processing.

    Attributes:
        text: Transcribed text.
        is_partial: Whether this is a partial (streaming) result.
        is_final: Whether this is the final result for a segment.
        confidence: Confidence score (0.0-1.0).
        timestamp_start: Start timestamp in seconds.
        timestamp_end: End timestamp in seconds.
        tokens: Raw text tokens.
    """

    text: str
    is_partial: bool
    is_final: bool
    confidence: float
    timestamp_start: float
    timestamp_end: float
    tokens: Optional[list[int]] = None


@dataclass
class STTSegment:
    """A complete speech segment with timestamps.

    Attributes:
        text: Full transcribed text for the segment.
        words: List of timestamped words.
        start_time: Segment start time in seconds.
        end_time: Segment end time in seconds.
        confidence: Average confidence score.
    """

    text: str
    words: list[dict]
    start_time: float
    end_time: float
    confidence: float


class STTModelBase(ABC):
    """Abstract base class for STT models.

    All STT implementations must inherit from this class and implement
    the required methods.
    """

    def __init__(self, config: STTConfig):
        """Initialize the STT model.

        Args:
            config: STT configuration.
        """
        self.config = config
        self._initialized = False
        self._streaming_active = False

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the model and load weights.

        This method should load the model onto the configured device
        and prepare it for inference.
        """
        pass

    @abstractmethod
    async def start_stream(self, session_id: str) -> None:
        """Start a new streaming session.

        Args:
            session_id: Unique session identifier.

        Raises:
            RuntimeError: If model is not initialized.
        """
        pass

    @abstractmethod
    async def process_audio_chunk(
        self,
        audio: np.ndarray,
        session_id: str,
    ) -> Optional[STTResult]:
        """Process an audio chunk in streaming mode.

        Args:
            audio: Audio chunk as float32 numpy array.
            session_id: Session identifier.

        Returns:
            STTResult if text is available, None otherwise.

        Raises:
            RuntimeError: If streaming is not active for the session.
        """
        pass

    @abstractmethod
    async def finalize_stream(
        self,
        session_id: str,
    ) -> STTResult:
        """Finalize a streaming session and get final result.

        Args:
            session_id: Session identifier.

        Returns:
            Final STTResult with complete transcription.

        Raises:
            RuntimeError: If streaming is not active for the session.
        """
        pass

    @abstractmethod
    async def end_stream(self, session_id: str) -> None:
        """End a streaming session and clean up resources.

        Args:
            session_id: Session identifier.
        """
        pass

    @abstractmethod
    async def transcribe(
        self,
        audio: np.ndarray,
    ) -> STTSegment:
        """Transcribe a complete audio file (non-streaming).

        Args:
            audio: Complete audio as float32 numpy array.

        Returns:
            STTSegment with complete transcription and timestamps.

        Raises:
            RuntimeError: If model is not initialized.
        """
        pass

    @abstractmethod
    async def switch_model(self, new_model_name: STTModelName) -> None:
        """Switch to a different model variant.

        This should gracefully drain active sessions before switching.

        Args:
            new_model_name: Name of the model to switch to.

        Raises:
            RuntimeError: If model is not initialized or sessions are active.
        """
        pass

    @abstractmethod
    def get_model_info(self) -> dict:
        """Get information about the current model.

        Returns:
            Dictionary with model information (name, device, params, etc).
        """
        pass

    @property
    def is_initialized(self) -> bool:
        """Check if the model is initialized."""
        return self._initialized

    @property
    def is_streaming(self) -> bool:
        """Check if any streaming sessions are active."""
        return self._streaming_active

    async def ensure_initialized(self) -> None:
        """Ensure the model is initialized, initialize if not.

        Raises:
            RuntimeError: If initialization fails.
        """
        if not self._initialized:
            await self.initialize()


class STTModelManager:
    """Manages STT model lifecycle and switching.

    Features:
    - Model loading and initialization
    - Graceful model switching with session draining
    - Model warmup on startup
    - Active session tracking
    """

    def __init__(self, model: STTModelBase):
        """Initialize the model manager.

        Args:
            model: STT model instance to manage.
        """
        self.model = model
        self._active_sessions: set[str] = set()
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the managed model."""
        await self.model.initialize()

    async def start_stream(self, session_id: str) -> None:
        """Start a streaming session.

        Args:
            session_id: Session identifier.
        """
        async with self._lock:
            await self.model.start_stream(session_id)
            self._active_sessions.add(session_id)

    async def end_stream(self, session_id: str) -> None:
        """End a streaming session.

        Args:
            session_id: Session identifier.
        """
        async with self._lock:
            await self.model.end_stream(session_id)
            self._active_sessions.discard(session_id)

    async def drain_sessions(self, timeout_seconds: float = 5.0) -> bool:
        """Wait for all active sessions to complete.

        Args:
            timeout_seconds: Maximum time to wait.

        Returns:
            True if all sessions drained, False if timeout expired.
        """
        start_time = asyncio.get_event_loop().time()
        timeout_remaining = timeout_seconds

        while self._active_sessions:
            if timeout_remaining <= 0:
                return False

            await asyncio.sleep(0.1)
            elapsed = asyncio.get_event_loop().time() - start_time
            timeout_remaining = timeout_seconds - elapsed

        return True

    async def switch_model(
        self,
        new_model_name: STTModelName,
        drain_timeout_seconds: float = 5.0,
    ) -> bool:
        """Switch to a different model.

        Args:
            new_model_name: Name of the model to switch to.
            drain_timeout_seconds: Maximum time to wait for sessions to drain.

        Returns:
            True if switch succeeded, False otherwise.
        """
        async with self._lock:
            # Drain active sessions
            drained = await self.drain_sessions(drain_timeout_seconds)

            if not drained and self._active_sessions:
                # Force close remaining sessions
                for session_id in list(self._active_sessions):
                    try:
                        await self.model.end_stream(session_id)
                    except Exception:
                        pass
                self._active_sessions.clear()

            # Switch model
            await self.model.switch_model(new_model_name)
            return True

    @property
    def active_session_count(self) -> int:
        """Get number of active streaming sessions."""
        return len(self._active_sessions)

    @property
    def active_sessions(self) -> set[str]:
        """Get set of active session IDs."""
        return self._active_sessions.copy()
