"""Base interface for Text-to-Speech models.

Defines the abstract interface that all TTS model implementations must follow.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, AsyncIterator
from enum import Enum

import numpy as np


class TTSModelName(str, Enum):
    """Available TTS model names."""

    POCKET = "pocket"  # Pocket TTS (CPU-only, 100M params)


@dataclass
class TTSConfig:
    """Configuration for TTS model.

    Attributes:
        model_name: Name of the model to use.
        device: Device to run on (cpu only for Pocket TTS).
        voice_id: Voice identifier to use.
        speed: Speech speed multiplier (0.5 to 2.0).
        stability: Stability/CFG scale (0.0 to 1.0).
        pitch: Pitch adjustment (0.5 to 2.0).
        output_format: Audio output format (pcm_int16, pcm_float32, wav).
        sample_rate: Output sample rate in Hz.
    """

    model_name: TTSModelName
    device: str = "cpu"
    voice_id: str = "default"
    speed: float = 1.0
    stability: float = 1.0
    pitch: float = 1.0
    output_format: str = "pcm_int16"
    sample_rate: int = 24000


@dataclass
class TTSResult:
    """Result from TTS synthesis.

    Attributes:
        audio: Synthesized audio as bytes.
        format: Audio format (pcm_int16, pcm_float32, wav).
        sample_rate: Sample rate in Hz.
        duration: Audio duration in seconds.
        text: Input text that was synthesized.
    """

    audio: bytes
    format: str
    sample_rate: int
    duration: float
    text: str


@dataclass
class TTSChunk:
    """A chunk of streaming TTS audio.

    Attributes:
        audio: Audio chunk as bytes.
        format: Audio format.
        sample_rate: Sample rate in Hz.
        is_final: Whether this is the final chunk.
        text_offset: Character offset in input text.
    """

    audio: bytes
    format: str
    sample_rate: int
    is_final: bool
    text_offset: int


class TTSModelBase(ABC):
    """Abstract base class for TTS models.

    All TTS implementations must inherit from this class and implement
    the required methods.
    """

    def __init__(self, config: TTSConfig):
        """Initialize the TTS model.

        Args:
            config: TTS configuration.
        """
        self.config = config
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the model and load weights.

        This method should load the model and prepare it for inference.
        """
        pass

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize speech from text (non-streaming).

        Args:
            text: Text to synthesize.
            voice_id: Optional voice identifier (overrides config).

        Returns:
            TTSResult with synthesized audio.

        Raises:
            RuntimeError: If model is not initialized.
        """
        pass

    @abstractmethod
    async def synthesize_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
    ) -> AsyncIterator[TTSChunk]:
        """Synthesize speech from text with streaming output.

        Args:
            text: Text to synthesize.
            voice_id: Optional voice identifier (overrides config).

        Yields:
            TTSChunk with audio chunks.

        Raises:
            RuntimeError: If model is not initialized.
        """
        pass

    @abstractmethod
    async def list_voices(self) -> list[dict]:
        """List available voices.

        Returns:
            List of voice information dictionaries.
        """
        pass

    @abstractmethod
    async def load_voice(self, voice_path: str) -> str:
        """Load a custom voice from file.

        Args:
            voice_path: Path to voice file (.safetensors).

        Returns:
            Voice ID for the loaded voice.

        Raises:
            RuntimeError: If model is not initialized or voice loading fails.
        """
        pass

    @abstractmethod
    async def switch_voice(self, voice_id: str) -> None:
        """Switch to a different voice.

        Args:
            voice_id: Voice identifier to switch to.

        Raises:
            RuntimeError: If voice not found.
        """
        pass

    @abstractmethod
    def get_model_info(self) -> dict:
        """Get information about the current model.

        Returns:
            Dictionary with model information.
        """
        pass

    @property
    def is_initialized(self) -> bool:
        """Check if the model is initialized."""
        return self._initialized

    async def ensure_initialized(self) -> None:
        """Ensure the model is initialized, initialize if not.

        Raises:
            RuntimeError: If initialization fails.
        """
        if not self._initialized:
            await self.initialize()


class TTSModelManager:
    """Manages TTS model lifecycle and voice management.

    Features:
    - Model loading and initialization
    - Voice loading and switching
    - Active synthesis tracking
    - Thread-safe operation
    """

    def __init__(self, model: TTSModelBase):
        """Initialize the model manager.

        Args:
            model: TTS model instance to manage.
        """
        self.model = model
        self._active_syntheses: set[str] = set()
        self._lock = asyncio.Lock()
        self._loaded_voices: dict[str, dict] = {}

    async def initialize(self) -> None:
        """Initialize the managed model."""
        await self.model.initialize()

    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize speech from text.

        Args:
            text: Text to synthesize.
            voice_id: Optional voice identifier.
            session_id: Optional session identifier for tracking.

        Returns:
            TTSResult with synthesized audio.
        """
        async with self._lock:
            if session_id:
                self._active_syntheses.add(session_id)

        try:
            result = await self.model.synthesize(text, voice_id)
            return result
        finally:
            if session_id:
                async with self._lock:
                    self._active_syntheses.discard(session_id)

    async def synthesize_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> AsyncIterator[TTSChunk]:
        """Synthesize speech from text with streaming output.

        Args:
            text: Text to synthesize.
            voice_id: Optional voice identifier.
            session_id: Optional session identifier for tracking.

        Yields:
            TTSChunk with audio chunks.
        """
        async with self._lock:
            if session_id:
                self._active_syntheses.add(session_id)

        try:
            async for chunk in self.model.synthesize_stream(text, voice_id):
                yield chunk
        finally:
            if session_id:
                async with self._lock:
                    self._active_syntheses.discard(session_id)

    async def load_voice(self, voice_path: str) -> str:
        """Load a custom voice.

        Args:
            voice_path: Path to voice file.

        Returns:
            Voice ID for the loaded voice.
        """
        voice_id = await self.model.load_voice(voice_path)

        async with self._lock:
            self._loaded_voices[voice_id] = {"path": voice_path}

        return voice_id

    @property
    def active_synthesis_count(self) -> int:
        """Get number of active syntheses."""
        return len(self._active_syntheses)

    @property
    def loaded_voices(self) -> dict[str, dict]:
        """Get loaded voices information."""
        return self._loaded_voices.copy()
