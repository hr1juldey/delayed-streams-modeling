"""Rate limiting middleware for per-session limits."""

from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from config.settings import ServerSettings
from config.logging_config import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for per-session request limits.

    Tracks requests per session and enforces configurable limits.
    """

    def __init__(self, app, max_requests_per_minute: int = 100):
        super().__init__(app)
        self.max_requests_per_minute = max_requests_per_minute
        self.session_requests = defaultdict(list)
        self.settings = ServerSettings()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and apply rate limiting.

        Args:
            request: The incoming request.
            call_next: The next middleware or route handler.

        Returns:
            The response from the next handler.

        Raises:
            HTTPException: If rate limit is exceeded.
        """
        # Skip rate limiting for health and metrics endpoints
        if request.url.path in ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        # Extract session ID from request
        session_id = self._extract_session_id(request)

        if session_id:
            # Check rate limit
            if self._is_rate_limited(session_id):
                logger.warning(f"Rate limit exceeded for session: {session_id}")
                from fastapi import HTTPException, status

                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Maximum {self.max_requests_per_minute} requests per minute.",
                )

            # Record request
            import time

            self.session_requests[session_id].append(time.time())

            # Clean old requests (older than 1 minute)
            self._clean_old_requests(session_id)

        return await call_next(request)

    def _extract_session_id(self, request: Request) -> str | None:
        """Extract session ID from request.

        Args:
            request: The incoming request.

        Returns:
            The session ID if available, None otherwise.
        """
        # Try to get from header
        session_id = request.headers.get("X-Session-ID")
        if session_id:
            return session_id

        # Try to get from query parameter
        session_id = request.query_params.get("session_id")
        if session_id:
            return session_id

        return None

    def _is_rate_limited(self, session_id: str) -> bool:
        """Check if session has exceeded rate limit.

        Args:
            session_id: The session ID to check.

        Returns:
            True if rate limited, False otherwise.
        """
        import time

        requests = self.session_requests[session_id]
        now = time.time()

        # Count requests in the last minute
        recent_requests = [r for r in requests if now - r < 60]

        return len(recent_requests) >= self.max_requests_per_minute

    def _clean_old_requests(self, session_id: str) -> None:
        """Clean up old request timestamps.

        Args:
            session_id: The session ID to clean.
        """
        import time

        if session_id in self.session_requests:
            now = time.time()
            self.session_requests[session_id] = [
                r for r in self.session_requests[session_id]
                if now - r < 60
            ]
