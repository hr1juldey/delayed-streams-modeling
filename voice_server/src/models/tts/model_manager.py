"""TTS Model Manager for lifecycle management and voice management.

Manages TTS model loading, voice loading/switching, and operations.
"""

import asyncio
from typing import Optional, AsyncIterator

from voice_server.config.logging_config import get_logger
from voice_server.config.settings import TTSSettings
from voice_server.src.models.tts.base import TTSModelBase, TTSConfig, TTSModelName, TTSResult, TTSChunk
from voice_server.src.models.tts.pocket import PocketTTSModel
from voice_server.src.core.exceptions import ModelException

logger = get_logger(__name__)


class TTSModelManager:
    """Manages TTS model lifecycle and operations.

    Features:
    - Model loading and initialization
    - Voice loading and management
    - Speech synthesis (streaming and non-streaming)
    - Voice parameter controls
    """

    def __init__(self, settings: TTSSettings):
        """Initialize the TTS model manager.

        Args:
            settings: TTS configuration settings.
        """
        self.settings = settings
        self._model: Optional[PocketTTSModel] = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize and load the TTS model.

        Raises:
            ModelException: If model initialization fails.
        """
        if self._model is not None:
            logger.warning("TTS model already initialized")
            return

        try:
            # Create config from settings
            config = TTSConfig(
                model_name=TTSModelName.POCKET,
                device="cpu",  # Pocket TTS is CPU-only
                voice_id=self.settings.default_voice,
                speed=self.settings.speed,
                stability=self.settings.stability,
                pitch=self.settings.pitch,
                output_format="pcm_int16",  # Can be overridden per request
                sample_rate=24000,
            )

            # Create and initialize model
            self._model = PocketTTSModel(config)
            await self._model.initialize()

            # Set voices path if configured
            # (voices_path will be set from ServerSettings during startup)

            logger.info("TTS model manager initialized: Pocket TTS")

        except Exception as e:
            logger.error(f"Failed to initialize TTS model manager: {e}")
            raise ModelException(f"Failed to initialize TTS: {e}") from e

    async def set_voices_path(self, voices_path: str) -> None:
        """Set the path for custom voice files.

        Args:
            voices_path: Directory path for voice files.
        """
        if self._model is None:
            logger.warning("Cannot set voices path: model not initialized")
            return

        self._model.set_voices_path(voices_path)
        logger.info(f"TTS voices path set to: {voices_path}")

    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        output_format: str = "pcm_int16",
        session_id: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize speech from text.

        Args:
            text: Text to synthesize.
            voice_id: Optional voice identifier.
            output_format: Audio output format.
            session_id: Optional session identifier for tracking.

        Returns:
            TTSResult with synthesized audio.

        Raises:
            ModelException: If synthesis fails.
        """
        if self._model is None:
            raise ModelException("TTS model not initialized")

        # Update config for this request
        original_format = self._model.config.output_format
        self._model.config.output_format = output_format

        try:
            result = await self._model.synthesize(text, voice_id)
            return result
        finally:
            self._model.config.output_format = original_format

    async def synthesize_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
        output_format: str = "pcm_int16",
        session_id: Optional[str] = None,
    ) -> AsyncIterator[TTSChunk]:
        """Synthesize speech from text with streaming output.

        Args:
            text: Text to synthesize.
            voice_id: Optional voice identifier.
            output_format: Audio output format.
            session_id: Optional session identifier for tracking.

        Yields:
            TTSChunk with audio chunks.

        Raises:
            ModelException: If synthesis fails.
        """
        if self._model is None:
            raise ModelException("TTS model not initialized")

        # Update config for this request
        original_format = self._model.config.output_format
        self._model.config.output_format = output_format

        try:
            async for chunk in self._model.synthesize_stream(text, voice_id):
                yield chunk
        finally:
            self._model.config.output_format = original_format

    async def list_voices(self) -> list[dict]:
        """List available voices.

        Returns:
            List of voice information dictionaries.

        Raises:
            ModelException: If model not initialized.
        """
        if self._model is None:
            raise ModelException("TTS model not initialized")

        return await self._model.list_voices()

    async def load_voice(self, voice_path: str) -> str:
        """Load a custom voice from file.

        Args:
            voice_path: Path to voice file (.safetensors).

        Returns:
            Voice ID for the loaded voice.

        Raises:
            ModelException: If voice loading fails.
        """
        if self._model is None:
            raise ModelException("TTS model not initialized")

        return await self._model.load_voice(voice_path)

    async def switch_voice(self, voice_id: str) -> None:
        """Switch to a different voice.

        Args:
            voice_id: Voice identifier to switch to.

        Raises:
            ModelException: If voice not found.
        """
        if self._model is None:
            raise ModelException("TTS model not initialized")

        await self._model.switch_voice(voice_id)
        logger.info(f"Switched to voice: {voice_id}")

    def set_voice_parameters(
        self,
        speed: Optional[float] = None,
        stability: Optional[float] = None,
        pitch: Optional[float] = None,
    ) -> None:
        """Set voice synthesis parameters.

        Args:
            speed: Speech speed multiplier (0.5 to 2.0).
            stability: Stability/CFG scale (0.0 to 1.0).
            pitch: Pitch adjustment (0.5 to 2.0).
        """
        if self._model is None:
            logger.warning("Cannot set voice parameters: model not initialized")
            return

        if speed is not None:
            self._model.config.speed = max(0.5, min(2.0, speed))

        if stability is not None:
            self._model.config.stability = max(0.0, min(1.0, stability))

        if pitch is not None:
            self._model.config.pitch = max(0.5, min(2.0, pitch))

        logger.debug(
            f"Voice parameters updated: speed={self._model.config.speed}, "
            f"stability={self._model.config.stability}, pitch={self._model.config.pitch}"
        )

    def get_model_info(self) -> dict:
        """Get information about the current model.

        Returns:
            Dictionary with model information.
        """
        if self._model is None:
            return {
                "is_initialized": False,
                "model_name": None,
            }

        info = self._model.get_model_info()
        return info

    @property
    def is_initialized(self) -> bool:
        """Check if the model manager is initialized."""
        return self._model is not None and self._model.is_initialized

    @property
    def current_voice_id(self) -> Optional[str]:
        """Get the current voice ID."""
        if self._model is None:
            return None
        return self._model.config.voice_id

    async def shutdown(self) -> None:
        """Shutdown the model manager and cleanup resources."""
        if self._model is None:
            return

        logger.info("Shutting down TTS model manager...")

        # Shutdown model
        await self._model.shutdown()

        # Clear model reference
        self._model = None

        logger.info("TTS model manager shutdown complete")


# Global TTS model manager instance
_tts_model_manager: Optional[TTSModelManager] = None


async def get_tts_model_manager(settings: TTSSettings | None = None) -> TTSModelManager:
    """Get the global TTS model manager.

    Args:
        settings: Ignored - kept for compatibility. Settings from initialization are used.

    Returns:
        TTSModelManager instance.

    Raises:
        RuntimeError: If manager has not been initialized.
    """
    global _tts_model_manager

    if _tts_model_manager is None:
        raise RuntimeError("TTS model manager not initialized. Call set_tts_model_manager first.")

    return _tts_model_manager


def set_tts_model_manager(manager: TTSModelManager) -> None:
    """Set the global TTS model manager instance.

    Args:
        manager: TTSModelManager instance to set.
    """
    global _tts_model_manager
    _tts_model_manager = manager
