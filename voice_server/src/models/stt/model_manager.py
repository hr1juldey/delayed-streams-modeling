"""STT Model Manager for lifecycle management and graceful switching.

Manages STT model loading, warmup, and switching with session draining.
"""

import asyncio
from typing import Optional

from voice_server.config.logging_config import get_logger
from voice_server.config.settings import STTSettings
from voice_server.src.models.stt.base import STTModelBase, STTConfig, STTModelName
from voice_server.src.models.stt.kyutai import KyutaiSTTModel
from voice_server.src.core.exceptions import ModelException

logger = get_logger(__name__)


class STTModelManager:
    """Manages STT model lifecycle and operations.

    Features:
    - Model loading and initialization
    - Warmup on startup
    - Graceful model switching with session draining
    - Active session tracking
    - Model info retrieval
    """

    def __init__(self, settings: STTSettings):
        """Initialize the STT model manager.

        Args:
            settings: STT configuration settings.
        """
        self.settings = settings
        self._model: Optional[KyutaiSTTModel] = None
        self._current_model_name: Optional[STTModelName] = None
        self._lock = asyncio.Lock()
        self._active_sessions: set[str] = set()

    async def initialize(self) -> None:
        """Initialize and load the STT model.

        Loads the model configured in settings and optionally warms it up.

        Raises:
            ModelException: If model initialization fails.
        """
        if self._model is not None:
            logger.warning("STT model already initialized")
            return

        try:
            # Create config from settings
            model_name = STTModelName(self.settings.model_name)
            config = STTConfig(
                model_name=model_name,
                device=self.settings.device,
                vad_mode=self.settings.vad_mode,
                streaming_mode=self.settings.streaming_mode,
                confidence_threshold=self.settings.confidence_threshold,
                target_latency_ms=self.settings.target_latency_ms,
            )

            # Create and initialize model
            self._model = KyutaiSTTModel(config)
            await self._model.initialize()

            self._current_model_name = model_name

            # Warmup if configured
            if self.settings.warmup_on_startup:
                await self._warmup()

            logger.info(
                f"STT model manager initialized: {model_name.value} on {self.settings.device}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize STT model manager: {e}")
            raise ModelException(f"Failed to initialize STT: {e}") from e

    async def _warmup(self) -> None:
        """Perform model warmup with a dummy inference.

        This ensures the model is fully loaded and ready before accepting requests.
        """
        if self._model is None:
            return

        try:
            logger.info("Warming up STT model...")

            # Create dummy audio (100ms of silence at 24kHz)
            import numpy as np

            dummy_audio = np.zeros(2400, dtype=np.float32)

            # Create a temporary session for warmup
            warmup_session = "_warmup"
            await self._model.start_stream(warmup_session)

            # Process dummy chunk
            await self._model.process_audio_chunk(dummy_audio, warmup_session)

            # Finalize and cleanup
            await self._model.finalize_stream(warmup_session)
            await self._model.end_stream(warmup_session)

            logger.info("STT model warmup complete")

        except Exception as e:
            logger.warning(f"STT model warmup failed (non-critical): {e}")

    async def start_stream(self, session_id: str) -> None:
        """Start a new streaming session.

        Args:
            session_id: Unique session identifier.

        Raises:
            ModelException: If model is not initialized.
        """
        if self._model is None:
            raise ModelException("STT model not initialized")

        await self._model.start_stream(session_id)
        self._active_sessions.add(session_id)

        logger.debug(f"Started STT stream: {session_id}")

    async def process_audio(
        self,
        audio,
        session_id: str,
    ):
        """Process an audio chunk for a streaming session.

        Args:
            audio: Audio chunk as numpy array.
            session_id: Session identifier.

        Returns:
            STTResult if text available, None otherwise.

        Raises:
            ModelException: If processing fails.
        """
        if self._model is None:
            raise ModelException("STT model not initialized")

        return await self._model.process_audio_chunk(audio, session_id)

    async def finalize_stream(self, session_id: str):
        """Finalize a streaming session and get final result.

        Args:
            session_id: Session identifier.

        Returns:
            Final STTResult.

        Raises:
            ModelException: If finalization fails.
        """
        if self._model is None:
            raise ModelException("STT model not initialized")

        result = await self._model.finalize_stream(session_id)
        return result

    async def end_stream(self, session_id: str) -> None:
        """End a streaming session.

        Args:
            session_id: Session identifier.
        """
        if self._model is None:
            return

        await self._model.end_stream(session_id)
        self._active_sessions.discard(session_id)

        logger.debug(f"Ended STT stream: {session_id}")

    async def transcribe(self, audio):
        """Transcribe a complete audio file.

        Args:
            audio: Audio as numpy array.

        Returns:
            STTSegment with transcription and timestamps.

        Raises:
            ModelException: If transcription fails.
        """
        if self._model is None:
            raise ModelException("STT model not initialized")

        return await self._model.transcribe(audio)

    async def drain_sessions(self, timeout_seconds: float = 5.0) -> bool:
        """Wait for all active sessions to complete.

        Args:
            timeout_seconds: Maximum time to wait.

        Returns:
            True if all sessions drained, False if timeout.
        """
        if not self._active_sessions:
            return True

        logger.info(f"Draining {len(self._active_sessions)} STT sessions...")

        start_time = asyncio.get_event_loop().time()
        timeout_remaining = timeout_seconds

        while self._active_sessions:
            if timeout_remaining <= 0:
                logger.warning(
                    f"Session drain timeout, {len(self._active_sessions)} sessions remaining"
                )
                return False

            await asyncio.sleep(0.1)
            elapsed = asyncio.get_event_loop().time() - start_time
            timeout_remaining = timeout_seconds - elapsed

        logger.info("All STT sessions drained")
        return True

    async def switch_model(
        self,
        new_model_name: str,
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
            if self._model is None:
                logger.warning("No model loaded, cannot switch")
                return False

            # Check if already using this model
            target_model = STTModelName(new_model_name)
            if target_model == self._current_model_name:
                logger.info(f"Already using model: {new_model_name}")
                return True

            logger.info(f"Switching STT model: {self._current_model_name} -> {new_model_name}")

            # Drain active sessions
            drained = await self.drain_sessions(drain_timeout_seconds)

            if not drained and self._active_sessions:
                # Force close remaining sessions
                logger.warning(
                    f"Force closing {len(self._active_sessions)} remaining sessions"
                )
                for session_id in list(self._active_sessions):
                    try:
                        await self.end_stream(session_id)
                    except Exception as e:
                        logger.error(f"Error closing session {session_id}: {e}")

            # Create new config
            config = STTConfig(
                model_name=target_model,
                device=self.settings.device,
                vad_mode=self.settings.vad_mode,
                streaming_mode=self.settings.streaming_mode,
                confidence_threshold=self.settings.confidence_threshold,
                target_latency_ms=self.settings.target_latency_ms,
            )

            # Create and initialize new model
            try:
                new_model = KyutaiSTTModel(config)
                await new_model.initialize()

                # Swap models
                self._model = new_model
                self._current_model_name = target_model

                logger.info(f"STT model switched successfully: {new_model_name}")
                return True

            except Exception as e:
                logger.error(f"Failed to switch STT model: {e}")
                raise ModelException(f"Failed to switch model: {e}") from e

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
        info["active_sessions"] = list(self._active_sessions)
        return info

    @property
    def is_initialized(self) -> bool:
        """Check if the model manager is initialized."""
        return self._model is not None and self._model.is_initialized

    @property
    def active_session_count(self) -> int:
        """Get number of active streaming sessions."""
        return len(self._active_sessions)

    @property
    def active_sessions(self) -> set[str]:
        """Get set of active session IDs."""
        return self._active_sessions.copy()

    async def shutdown(self) -> None:
        """Shutdown the model manager and cleanup resources.

        This will end all active sessions.
        """
        if self._model is None:
            return

        logger.info("Shutting down STT model manager...")

        # End all active sessions
        for session_id in list(self._active_sessions):
            try:
                await self.end_stream(session_id)
            except Exception as e:
                logger.error(f"Error ending session {session_id}: {e}")

        # Clear model reference
        self._model = None
        self._current_model_name = None

        logger.info("STT model manager shutdown complete")


# Global STT model manager instance
_stt_model_manager: Optional[STTModelManager] = None


async def get_stt_model_manager(settings: STTSettings | None = None) -> STTModelManager:
    """Get the global STT model manager.

    Args:
        settings: Ignored - kept for compatibility. Settings from initialization are used.

    Returns:
        STTModelManager instance.

    Raises:
        RuntimeError: If manager has not been initialized.
    """
    global _stt_model_manager

    if _stt_model_manager is None:
        raise RuntimeError("STT model manager not initialized. Call set_stt_model_manager first.")

    return _stt_model_manager


def set_stt_model_manager(manager: STTModelManager) -> None:
    """Set the global STT model manager instance.

    Args:
        manager: STTModelManager instance to set.
    """
    global _stt_model_manager
    _stt_model_manager = manager
