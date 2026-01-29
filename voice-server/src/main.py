"""FastAPI application entry point for the voice server."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.logging_config import LoggingSettings, setup_logging
from config.settings import ServerSettings

# Setup logging
logging_settings = LoggingSettings()
setup_logging(logging_settings)

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
    # TODO: Load STT and TTS models if preload_model is true
    # TODO: Start background cleanup task for expired sessions
    print("Voice Server starting up...")
    yield
    # TODO: Graceful shutdown with connection draining
    # TODO: Unload models and cleanup resources
    print("Voice Server shutting down...")


app.router.lifespan_context = lifespan


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with server information."""
    return {
        "name": "Voice Server",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


# TODO: Import and register routes
# from src.api.routes import health, voice, websocket_stt, websocket_tts
# app.include_router(health.router, tags=["health"])
# app.include_router(voice.router, prefix="/api/v1", tags=["voice"])
# app.include_router(websocket_stt.router, tags=["websocket-stt"])
# app.include_router(websocket_tts.router, tags=["websocket-tts"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,  # Enable reload for development
        log_level=logging_settings.level.lower(),
    )
