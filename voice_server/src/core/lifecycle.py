"""Startup and shutdown handlers for model loading and cleanup."""

import asyncio

from voice_server.config.logging_config import get_logger
from voice_server.config.settings import ServerSettings

logger = get_logger(__name__)


class LifecycleManager:
    """Manages application lifecycle including model loading and cleanup."""

    def __init__(self, settings: ServerSettings) -> None:
        """Initialize the lifecycle manager.

        Args:
            settings: Server settings.
        """
        self.settings = settings
        self.stt_model = None
        self.tts_model = None
        self._cleanup_task = None

    async def startup(self) -> None:
        """Handle application startup.

        Loads STT and TTS models if configured to preload.
        Starts background cleanup task for expired sessions.
        """
        logger.info("Starting Voice Server lifecycle...")

        # TODO: Load STT model if preload_model is true
        if self.settings.stt.preload_model:
            logger.info(f"Loading STT model: {self.settings.stt.model_name}")
            # await self._load_stt_model()

        # TODO: Load TTS model if preload_model is true
        if self.settings.tts.preload_model:
            logger.info("Loading TTS model (Pocket TTS)")
            # await self._load_tts_model()

        # Start background cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("Voice Server startup complete")

    async def shutdown(self) -> None:
        """Handle application shutdown.

        Performs graceful shutdown with connection draining.
        Unloads models and cleans up resources.
        """
        logger.info("Shutting down Voice Server...")

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # TODO: Drain active WebSocket connections
        logger.info("Draining active connections...")
        # await self._drain_connections()

        # TODO: Unload models
        logger.info("Unloading models...")
        # await self._unload_stt_model()
        # await self._unload_tts_model()

        logger.info("Voice Server shutdown complete")

    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired sessions.

        Runs periodically to check for sessions that have timed out
        and removes them from memory/storage.
        """
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                # TODO: Implement session cleanup logic
                # await self._cleanup_expired_sessions()

            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")


# Global lifecycle manager instance
_lifecycle_manager: LifecycleManager | None = None


def get_lifecycle_manager() -> LifecycleManager:
    """Get the global lifecycle manager instance.

    Returns:
        The LifecycleManager instance.

    Raises:
        RuntimeError: If the lifecycle manager has not been initialized.
    """
    global _lifecycle_manager
    if _lifecycle_manager is None:
        raise RuntimeError("Lifecycle manager not initialized")
    return _lifecycle_manager


def set_lifecycle_manager(manager: LifecycleManager) -> None:
    """Set the global lifecycle manager instance.

    Args:
        manager: The LifecycleManager instance to set.
    """
    global _lifecycle_manager
    _lifecycle_manager = manager
