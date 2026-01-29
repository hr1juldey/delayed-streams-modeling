"""Session store implementations for persisting session data.

Provides abstract interface and implementations for SQLite and in-memory storage.
"""

import asyncio
import aiosqlite
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any

from voice_server.config.logging_config import get_logger
from voice_server.src.services.session.models import SessionHistory, SessionState, SessionStatus

logger = get_logger(__name__)


class SessionStoreBase(ABC):
    """Abstract base class for session storage."""

    @abstractmethod
    async def create_session(self, session_id: str) -> SessionHistory:
        """Create a new session history.

        Args:
            session_id: Session identifier.

        Returns:
            Created SessionHistory.
        """
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[SessionHistory]:
        """Get session history by ID.

        Args:
            session_id: Session identifier.

        Returns:
            SessionHistory if found, None otherwise.
        """
        pass

    @abstractmethod
    async def update_session(self, history: SessionHistory) -> None:
        """Update session history.

        Args:
            history: Session history to update.
        """
        pass

    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        """Delete session history.

        Args:
            session_id: Session identifier.
        """
        pass

    @abstractmethod
    async def list_sessions(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SessionHistory]:
        """List session histories.

        Args:
            limit: Maximum number of sessions to return.
            offset: Offset for pagination.

        Returns:
            List of SessionHistory.
        """
        pass

    @abstractmethod
    async def cleanup_old_sessions(self, max_age_seconds: float) -> int:
        """Delete sessions older than max age.

        Args:
            max_age_seconds: Maximum age in seconds.

        Returns:
            Number of sessions deleted.
        """
        pass


class InMemorySessionStore(SessionStoreBase):
    """In-memory session store for testing and development.

    Not persistent across restarts. Suitable for testing and
    scenarios where persistence is not required.
    """

    def __init__(self):
        """Initialize the in-memory store."""
        self._sessions: Dict[str, SessionHistory] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, session_id: str) -> SessionHistory:
        """Create a new session history."""
        async with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]

            history = SessionHistory(session_id=session_id)
            self._sessions[session_id] = history
            logger.debug(f"Created in-memory session: {session_id}")
            return history

    async def get_session(self, session_id: str) -> Optional[SessionHistory]:
        """Get session history by ID."""
        async with self._lock:
            return self._sessions.get(session_id)

    async def update_session(self, history: SessionHistory) -> None:
        """Update session history."""
        async with self._lock:
            self._sessions[history.session_id] = history

    async def delete_session(self, session_id: str) -> None:
        """Delete session history."""
        async with self._lock:
            self._sessions.pop(session_id, None)
            logger.debug(f"Deleted in-memory session: {session_id}")

    async def list_sessions(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SessionHistory]:
        """List session histories."""
        async with self._lock:
            sessions = list(self._sessions.values())
            sessions.sort(key=lambda s: s.updated_at, reverse=True)
            return sessions[offset:offset + limit]

    async def cleanup_old_sessions(self, max_age_seconds: float) -> int:
        """Delete sessions older than max age."""
        import time

        async with self._lock:
            cutoff = time.time() - max_age_seconds
            to_delete = [
                sid for sid, hist in self._sessions.items()
                if hist.updated_at < cutoff
            ]

            for sid in to_delete:
                del self._sessions[sid]

            if to_delete:
                logger.info(f"Cleaned up {len(to_delete)} old in-memory sessions")

            return len(to_delete)


class SQLiteSessionStore(SessionStoreBase):
    """SQLite-based persistent session store.

    Provides persistent storage for session histories across restarts.
    """

    def __init__(self, db_path: str = "./data/db/sessions.db"):
        """Initialize the SQLite store.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._conn: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize the database and create tables."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_updated_at
                ON sessions(updated_at DESC)
            """)
            await db.commit()

        logger.info(f"SQLite session store initialized: {self.db_path}")

    async def create_session(self, session_id: str) -> SessionHistory:
        """Create a new session history."""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                # Check if exists
                cursor = await db.execute(
                    "SELECT data FROM sessions WHERE session_id = ?",
                    (session_id,)
                )
                row = await cursor.fetchone()

                if row:
                    history = SessionHistory.from_dict(json.loads(row[0]))
                    return history

                # Create new
                history = SessionHistory(session_id=session_id)
                await self._save_session(db, history)
                await db.commit()

                logger.debug(f"Created SQLite session: {session_id}")
                return history

    async def get_session(self, session_id: str) -> Optional[SessionHistory]:
        """Get session history by ID."""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT data FROM sessions WHERE session_id = ?",
                    (session_id,)
                )
                row = await cursor.fetchone()

                if row:
                    return SessionHistory.from_dict(json.loads(row[0]))

                return None

    async def update_session(self, history: SessionHistory) -> None:
        """Update session history."""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await self._save_session(db, history)
                await db.commit()

    async def _save_session(self, db: aiosqlite.Connection, history: SessionHistory) -> None:
        """Save session to database.

        Args:
            db: Database connection.
            history: Session history to save.
        """
        data = json.dumps(history.to_dict())
        await db.execute(
            """INSERT OR REPLACE INTO sessions (session_id, data, created_at, updated_at)
               VALUES (?, ?, ?, ?)""",
            (history.session_id, data, history.created_at, history.updated_at)
        )

    async def delete_session(self, session_id: str) -> None:
        """Delete session history."""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM sessions WHERE session_id = ?",
                    (session_id,)
                )
                await db.commit()
                logger.debug(f"Deleted SQLite session: {session_id}")

    async def list_sessions(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SessionHistory]:
        """List session histories."""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    """SELECT data FROM sessions
                       ORDER BY updated_at DESC
                       LIMIT ? OFFSET ?""",
                    (limit, offset)
                )
                rows = await cursor.fetchall()

                return [SessionHistory.from_dict(json.loads(row[0])) for row in rows]

    async def cleanup_old_sessions(self, max_age_seconds: float) -> None:
        """Delete sessions older than max age."""
        import time

        async with self._lock:
            cutoff = time.time() - max_age_seconds

            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "DELETE FROM sessions WHERE updated_at < ?",
                    (cutoff,)
                )
                await db.commit()

                deleted = cursor.rowcount
                if deleted:
                    logger.info(f"Cleaned up {deleted} old SQLite sessions")


def create_session_store(
    backend: str = "sqlite",
    db_path: str = "./data/db/sessions.db",
) -> SessionStoreBase:
    """Create a session store instance.

    Args:
        backend: Storage backend ("sqlite" or "memory").
        db_path: Database path for SQLite backend.

    Returns:
        SessionStoreBase instance.
    """
    if backend == "sqlite":
        return SQLiteSessionStore(db_path)
    elif backend == "memory":
        return InMemorySessionStore()
    else:
        raise ValueError(f"Unknown session store backend: {backend}")
