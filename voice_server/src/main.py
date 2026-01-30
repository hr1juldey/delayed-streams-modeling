"""FastAPI application entry point for the voice server."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from voice_server.config.logging_config import LoggingSettings, setup_logging, get_logger
from voice_server.config.settings import ServerSettings

# Setup logging
logging_settings = LoggingSettings()
setup_logging(logging_settings)
logger = get_logger(__name__)

# Load settings
settings = ServerSettings()

# Create FastAPI app
app = FastAPI(
    title="Voice Server",
    description="Real-time Speech-to-Text and Text-to-Speech WebSocket API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events for model loading and cleanup.
    """
    from voice_server.src.core.lifecycle import LifecycleManager, set_lifecycle_manager

    logger.info("Voice Server starting up...")

    # Create and initialize lifecycle manager
    lifecycle_manager = LifecycleManager(settings)
    set_lifecycle_manager(lifecycle_manager)

    # Initialize connection manager
    from voice_server.src.services.websocket.connection import ConnectionManager, set_connection_manager

    connection_manager = ConnectionManager(settings)
    set_connection_manager(connection_manager)
    logger.info("Connection manager initialized")

    # Initialize heartbeat monitor
    from voice_server.src.services.websocket.heartbeat import HeartbeatMonitor, set_heartbeat_monitor

    heartbeat_monitor = HeartbeatMonitor(connection_manager, settings)
    set_heartbeat_monitor(heartbeat_monitor)
    await heartbeat_monitor.start()
    logger.info("Heartbeat monitor started")

    # Initialize session manager
    from voice_server.src.services.session.manager import SessionManager, set_session_manager

    # Construct full database path from ServerSettings
    db_path = f"{settings.db_path}/sessions.db"
    session_manager = SessionManager(settings.session, db_path=db_path)
    set_session_manager(session_manager)
    await session_manager.initialize()
    logger.info("Session manager initialized")

    # Load STT model if preload is enabled
    if settings.stt.preload_model:
        from voice_server.src.models.stt.model_manager import STTModelManager, set_stt_model_manager

        logger.info("Preloading STT model...")
        stt_manager = STTModelManager(settings.stt)
        await stt_manager.initialize()
        set_stt_model_manager(stt_manager)
        logger.info(f"STT model loaded: {settings.stt.model_name}")

    # Load TTS model if preload is enabled
    if settings.tts.preload_model:
        from voice_server.src.models.tts.model_manager import TTSModelManager, set_tts_model_manager

        logger.info("Preloading TTS model...")
        tts_manager = TTSModelManager(settings.tts)
        await tts_manager.initialize()
        set_tts_model_manager(tts_manager)
        logger.info("TTS model loaded: Pocket TTS")

    # Run startup
    await lifecycle_manager.startup()

    logger.info("Voice Server startup complete")

    yield

    # Shutdown
    logger.info("Voice Server shutting down...")

    await lifecycle_manager.shutdown()

    # Stop heartbeat monitor
    await heartbeat_monitor.stop()

    # Shutdown session manager
    await session_manager.shutdown()

    # Shutdown model managers
    from voice_server.src.models.stt.model_manager import _stt_model_manager
    from voice_server.src.models.tts.model_manager import _tts_model_manager

    if _stt_model_manager:
        await _stt_model_manager.shutdown()

    if _tts_model_manager:
        await _tts_model_manager.shutdown()

    # Drain WebSocket connections
    await connection_manager.drain_all()

    logger.info("Voice Server shutdown complete")


app.router.lifespan_context = lifespan


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with server information."""
    return {
        "name": "Voice Server",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
        "stt_websocket": "/api/v1/ws/stt",
        "tts_websocket": "/api/v1/ws/tts",
    }


# Import and register routes
from voice_server.src.api.routes import health, voice

app.include_router(health.router, tags=["health"])
app.include_router(voice.router, tags=["voice"])

# STT and TTS WebSocket routes are self-registering
from voice_server.src.api.routes import websocket_stt, websocket_tts

app.include_router(websocket_stt.router, tags=["websocket-stt"])
app.include_router(websocket_tts.router, tags=["websocket-tts"])


# Add rate limiting middleware
from voice_server.src.api.middleware import RateLimitMiddleware

app.add_middleware(RateLimitMiddleware, max_requests_per_minute=100)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "voice_server.src.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,  # Enable reload for development
        log_level=logging_settings.level.lower(),
    )
