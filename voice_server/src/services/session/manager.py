"""Session manager for managing session lifecycle and state.

Provides session creation, retrieval, activity tracking, and cleanup.
"""

import asyncio
import time
import uuid
from typing import Optional, Dict, Any

from voice_server.config.logging_config import get_logger
from voice_server.config.settings import SessionSettings
from voice_server.src.services.session.models import (
    SessionState,
    SessionHistory,
    SessionStatus,
    ConversationTurn,
    SessionStats,
)
from voice_server.src.services.session.store import SessionStoreBase, create_session_store

logger = get_logger(__name__)


class SessionManager:
    """Manages WebSocket session lifecycle and state.

    Features:
    - Session creation and resumption
    - Activity tracking and timeout handling
    - Client-provided history support
    - Concurrent session limits
    - Background cleanup
    """

    def __init__(
        self,
        settings: SessionSettings,
        store: Optional[SessionStoreBase] = None,
        db_path: str = "./data/db/sessions.db",
    ):
        """Initialize the session manager.

        Args:
            settings: Session configuration settings.
            store: Optional session store. If not provided, creates from settings.
            db_path: Database path for SQLite backend (relative to CWD).
        """
        self.settings = settings
        self.store = store or create_session_store(
            backend=settings.storage_backend,
            db_path=db_path,
        )

        # Active sessions (in-memory)
        self._active_sessions: Dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

        # Statistics
        self._stats = SessionStats()

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize the session manager."""
        if isinstance(self.store, type(store := self.store)):
            # Initialize SQLite store
            await self.store.initialize()

        # Start background cleanup
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("Session manager initialized")

    async def shutdown(self) -> None:
        """Shutdown the session manager."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Session manager shutdown complete")

    async def create_or_resume_session(
        self,
        session_id: Optional[str],
        client_history: Optional[Dict[str, Any]] = None,
    ) -> SessionState:
        """Create a new session or resume an existing one.

        Args:
            session_id: Optional session ID to resume. If None, generates new ID.
            client_history: Optional client-provided history.

        Returns:
            SessionState for the session.
        """
        async with self._lock:
            # Check concurrent session limit
            active_count = len(self._active_sessions)
            if session_id not in self._active_sessions:
                if active_count >= self.settings.max_concurrent_sessions:
                    # Check for idle sessions to remove
                    await self._remove_idle_sessions()

                if len(self._active_sessions) >= self.settings.max_concurrent_sessions:
                    raise RuntimeError("Maximum session limit reached")

            # Generate session ID if not provided
            if not session_id:
                session_id = str(uuid.uuid4())

            # Check if already active
            if session_id in self._active_sessions:
                state = self._active_sessions[session_id]
                state.update_activity()
                logger.debug(f"Resumed active session: {session_id}")
                return state

            # Try to resume from store
            history = None

            if client_history and self.settings.history_required:
                # Use client-provided history
                logger.info(f"Using client-provided history for {session_id}")
                history = SessionHistory.from_dict(client_history)
            elif self.settings.recovery_enabled:
                # Try to recover from store
                stored = await self.store.get_session(session_id)
                if stored:
                    history = stored
                    logger.info(f"Resumed session from store: {session_id}")

            # Create new history if not found
            if not history:
                history = await self.store.create_session(session_id)

            # Create session state
            state = SessionState(
                session_id=session_id,
                status=SessionStatus.ACTIVE,
                history=history,
            )

            self._active_sessions[session_id] = state
            self._stats.total_sessions += 1
            self._stats.active_sessions = len(self._active_sessions)

            logger.info(
                f"Session created/resumed: {session_id}, "
                f"active={self._stats.active_sessions}"
            )

            return state

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get an active session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            SessionState if found, None otherwise.
        """
        async with self._lock:
            return self._active_sessions.get(session_id)

    async def update_session(self, session_id: str) -> None:
        """Update session activity timestamp.

        Args:
            session_id: Session identifier.
        """
        async with self._lock:
            state = self._active_sessions.get(session_id)
            if state:
                state.update_activity()

    async def add_conversation_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        audio_duration: Optional[float] = None,
    ) -> None:
        """Add a conversation turn to session history.

        Args:
            session_id: Session identifier.
            role: Role (user, assistant, system).
            content: Text content.
            audio_duration: Optional audio duration.
        """
        async with self._lock:
            state = self._active_sessions.get(session_id)
            if not state or not state.history:
                return

            # Create turn
            turn = ConversationTurn(
                turn_id=str(uuid.uuid4()),
                timestamp=time.time(),
                role=role,
                content=content,
                audio_duration=audio_duration,
            )

            # Add to history
            state.history.add_turn(turn)

            # Persist to store
            await self.store.update_session(state.history)

            # Update stats
            self._stats.total_turns += 1

            logger.debug(f"Added turn to session {session_id}: {role}")

    async def close_session(self, session_id: str) -> None:
        """Close an active session.

        Args:
            session_id: Session identifier.
        """
        async with self._lock:
            state = self._active_sessions.get(session_id)
            if not state:
                return

            state.status = SessionStatus.CLOSED
            del self._active_sessions[session_id]

            self._stats.active_sessions = len(self._active_sessions)
            self._stats.closed_sessions += 1

            logger.info(
                f"Session closed: {session_id}, "
                f"active={self._stats.active_sessions}"
            )

    async def _remove_idle_sessions(self) -> None:
        """Remove sessions that have been idle too long."""
        timeout_seconds = self.settings.timeout_minutes * 60
        now = time.time()

        to_remove = []
        for session_id, state in self._active_sessions.items():
            idle_time = now - state.last_activity
            if idle_time > timeout_seconds:
                to_remove.append(session_id)

        for session_id in to_remove:
            state = self._active_sessions.get(session_id)
            if state:
                state.status = SessionStatus.TIMEOUT
            del self._active_sessions[session_id]
            self._stats.timeout_sessions += 1
            logger.info(f"Session timed out: {session_id}")

        self._stats.active_sessions = len(self._active_sessions)

    async def _cleanup_loop(self) -> None:
        """Background task to clean up old sessions."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                # Remove idle sessions
                await self._remove_idle_sessions()

                # Cleanup old sessions from store
                max_age_seconds = self.settings.timeout_minutes * 60 * 24  # 24x timeout
                deleted = await self.store.cleanup_old_sessions(max_age_seconds)
                if deleted:
                    logger.info(f"Cleaned up {deleted} old sessions from store")

            except asyncio.CancelledError:
                logger.info("Session cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in session cleanup loop: {e}")

    def get_active_sessions(self) -> list[str]:
        """Get list of active session IDs."""
        return list(self._active_sessions.keys())

    def get_active_session_count(self) -> int:
        """Get number of active sessions."""
        return len(self._active_sessions)

    def get_stats(self) -> SessionStats:
        """Get session statistics.

        Returns:
            SessionStats with current metrics.
        """
        self._stats.active_sessions = len(self._active_sessions)
        return self._stats


# Global session manager instance
_session_manager: Optional[SessionManager] = None


async def get_session_manager(settings: SessionSettings) -> SessionManager:
    """Get or create the global session manager.

    Args:
        settings: Session configuration settings.

    Returns:
        SessionManager instance.
    """
    global _session_manager

    if _session_manager is None:
        _session_manager = SessionManager(settings)
        await _session_manager.initialize()

    return _session_manager


def set_session_manager(manager: SessionManager) -> None:
    """Set the global session manager instance.

    Args:
        manager: SessionManager instance to set.
    """
    global _session_manager
    _session_manager = manager
