"""API routes for the voice server."""

from src.api.routes import health, voice, websocket_stt, websocket_tts

__all__ = ["health", "voice", "websocket_stt", "websocket_tts"]
