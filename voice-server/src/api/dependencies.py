"""FastAPI dependencies for auth and session management."""

from fastapi import Depends, WebSocket, status

from config.settings import ServerSettings
from src.core.security import verify_api_key


async def get_websocket_auth(websocket: WebSocket) -> None:
    """Verify WebSocket authentication.

    Args:
        websocket: The WebSocket connection.

    Raises:
        WebSocketDisconnect: If authentication fails.
    """
    settings = ServerSettings()

    # Skip auth if not required
    if not settings.require_auth:
        return

    # Get API key from query parameter or header
    api_key = websocket.query_params.get("api_key")
    if not api_key:
        # Try to get from header
        headers = dict(websocket.headers)
        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]

    if not api_key:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing API key")
        raise ValueError("Missing API key")

    if api_key not in settings.api_keys:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid API key")
        raise ValueError("Invalid API key")


def get_current_session_id() -> str | None:
    """Get the current session ID from request state.

    Returns:
        The session ID if available, None otherwise.
    """
    # TODO: Implement session ID extraction from request state
    # This will be populated by WebSocket middleware
    return None
