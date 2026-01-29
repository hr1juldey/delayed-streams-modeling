"""API key authentication dependency for FastAPI."""

from typing import Annotated

from fastapi import Header, HTTPException, status

from voice_server.config.settings import ServerSettings
from voice_server.src.core.exceptions import AuthenticationException


async def verify_api_key(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Verify API key from Authorization header.

    Args:
        authorization: The Authorization header value.

    Raises:
        HTTPException: If authentication is required and fails.
    """
    settings = ServerSettings()

    # Skip auth if not required
    if not settings.require_auth:
        return

    # Check if API keys are configured
    if not settings.api_keys:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication required but no API keys configured",
        )

    # Extract token from "Bearer <token>" format
    token = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Use Authorization: Bearer <token> header.",
        )

    if token not in settings.api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
