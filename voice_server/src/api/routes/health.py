"""Health check and metrics endpoints for monitoring.

Provides /health and /metrics endpoints for server monitoring.
"""

import time
from typing import Dict, Any

from fastapi import APIRouter

from voice_server.config.logging_config import get_logger
from voice_server.src.utils.metrics import get_metrics_collector

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint.

    Returns server status and model information.

    Returns:
        Dictionary with health status.
    """
    from src.models.stt.model_manager import _stt_model_manager
    from src.models.tts.model_manager import _tts_model_manager
    from src.services.websocket.connection import _connection_manager
    from src.services.session.manager import _session_manager

    # Gather health information
    health = {
        "status": "ok",
        "timestamp": time.time(),
        "models": {},
        "sessions": {},
        "server": {},
    }

    # STT model status
    if _stt_model_manager is not None:
        health["models"]["stt"] = _stt_model_manager.get_model_info()
    else:
        health["models"]["stt"] = {"status": "not_loaded"}

    # TTS model status
    if _tts_model_manager is not None:
        health["models"]["tts"] = _tts_model_manager.get_model_info()
    else:
        health["models"]["tts"] = {"status": "not_loaded"}

    # Connection manager status
    if _connection_manager is not None:
        health["sessions"]["active_websockets"] = _connection_manager.connection_count
    else:
        health["sessions"]["active_websockets"] = 0

    # Session manager status
    if _session_manager is not None:
        health["sessions"]["active_sessions"] = _session_manager.get_active_session_count()
        health["sessions"]["stats"] = _session_manager.get_stats().to_dict()
    else:
        health["sessions"]["active_sessions"] = 0

    # Server info
    from config.settings import ServerSettings

    settings = ServerSettings()
    health["server"] = {
        "version": settings.api_version,
        "host": settings.host,
        "port": settings.port,
        "max_concurrent_sessions": settings.max_concurrent_sessions,
    }

    return health


@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint.

    Returns metrics in Prometheus text format.

    Returns:
        Metrics as plain text response.
    """
    from fastapi.responses import PlainTextResponse

    metrics_collector = get_metrics_collector()

    # Update current metrics
    from src.models.stt.model_manager import _stt_model_manager
    from src.models.tts.model_manager import _tts_model_manager
    from src.services.websocket.connection import _connection_manager
    from src.services.session.manager import _session_manager

    # Update session counts
    stt_sessions = 0
    tts_sessions = 0

    if _stt_model_manager is not None:
        stt_sessions = _stt_model_manager.active_session_count
        metrics_collector.update_model_status(
            "stt",
            _stt_model_manager._current_model_name.value if _stt_model_manager._current_model_name else "none",
            _stt_model_manager.is_initialized,
        )

    if _tts_model_manager is not None:
        tts_sessions = _tts_model_manager.current_voice_id is not None if 0 else 0  # Simplified
        metrics_collector.update_model_status(
            "tts",
            "pocket",
            _tts_model_manager.is_initialized,
        )

    metrics_collector.update_active_sessions(stt_sessions, tts_sessions)

    # Get metrics text
    metrics_text = metrics_collector.get_metrics_text()

    return PlainTextResponse(
        content=metrics_text,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/status")
async def server_status() -> Dict[str, Any]:
    """Detailed server status endpoint.

    Returns comprehensive server status including all components.

    Returns:
        Dictionary with detailed status.
    """
    health = await health_check()

    # Add additional status information
    from src.services.websocket.heartbeat import _heartbeat_monitor

    if _heartbeat_monitor is not None:
        health["heartbeat"] = _heartbeat_monitor.get_health_summary()

    return health
