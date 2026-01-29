"""WebSocket connection manager for handling multiple concurrent sessions.

Provides session tracking, message routing, and broadcast capabilities.
"""

import asyncio
from typing import Dict, Set, Optional
from fastapi import WebSocket

from config.logging_config import get_logger
from config.settings import ServerSettings
from src.services.websocket.protocol import Message, MessageProtocol, MessageType

logger = get_logger(__name__)


class ConnectionInfo:
    """Information about a connected WebSocket session.

    Attributes:
        websocket: The WebSocket connection instance.
        session_id: Unique session identifier.
        protocol: Message protocol instance for encoding/decoding.
        connected_at: Timestamp when connection was established.
        last_activity: Timestamp of last activity (message sent/received).
    """

    def __init__(
        self,
        websocket: WebSocket,
        session_id: str,
        protocol: MessageProtocol,
    ):
        self.websocket = websocket
        self.session_id = session_id
        self.protocol = protocol
        self.connected_at = asyncio.get_event_loop().time()
        self.last_activity = self.connected_at

    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = asyncio.get_event_loop().time()

    @property
    def idle_time(self) -> float:
        """Get idle time in seconds."""
        return asyncio.get_event_loop().time() - self.last_activity


class ConnectionManager:
    """Manages WebSocket connections and session routing.

    Features:
    - Session-based connection tracking
    - Message routing to specific sessions
    - Broadcast capabilities
    - Connection lifecycle management
    - Activity monitoring and cleanup
    """

    def __init__(self, settings: ServerSettings | None = None):
        """Initialize the connection manager.

        Args:
            settings: Optional server settings. If not provided, creates default.
        """
        self.settings = settings or ServerSettings()
        self._connections: Dict[str, ConnectionInfo] = {}
        self._session_to_websocket: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        encoding: str = "json",
    ) -> ConnectionInfo:
        """Accept and register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept.
            session_id: Unique session identifier.
            encoding: Message encoding format ("json" or "msgpack").

        Returns:
            ConnectionInfo instance for the new connection.

        Raises:
            RuntimeError: If session limit is reached.
        """
        async with self._lock:
            # Check session limit
            if len(self._connections) >= self.settings.max_concurrent_sessions:
                logger.warning(
                    f"Session limit reached: {self.settings.max_concurrent_sessions}"
                )
                await websocket.close(
                    code=1013, reason="Server at maximum session capacity"
                )
                raise RuntimeError("Maximum session limit reached")

            # Check if session already exists
            if session_id in self._connections:
                logger.warning(f"Session already connected: {session_id}")
                await websocket.close(code=1008, reason="Session already active")
                raise ValueError(f"Session {session_id} already connected")

            # Accept the connection
            await websocket.accept()

            # Create protocol instance
            protocol = MessageProtocol(encoding=encoding)

            # Create connection info
            conn_info = ConnectionInfo(
                websocket=websocket,
                session_id=session_id,
                protocol=protocol,
            )

            # Register connection
            self._connections[session_id] = conn_info
            self._session_to_websocket[session_id] = websocket

            logger.info(
                f"WebSocket connected: session={session_id}, "
                f"encoding={encoding}, "
                f"total={len(self._connections)}"
            )

            return conn_info

    async def disconnect(self, session_id: str) -> None:
        """Disconnect and remove a session.

        Args:
            session_id: Session identifier to disconnect.
        """
        async with self._lock:
            if session_id in self._connections:
                conn_info = self._connections[session_id]

                try:
                    await conn_info.websocket.close(code=1000, reason="Normal closure")
                except Exception as e:
                    logger.warning(f"Error closing websocket for {session_id}: {e}")

                del self._connections[session_id]
                if session_id in self._session_to_websocket:
                    del self._session_to_websocket[session_id]

                logger.info(
                    f"WebSocket disconnected: session={session_id}, "
                    f"remaining={len(self._connections)}"
                )

    async def send_message(self, session_id: str, message: Message) -> bool:
        """Send a message to a specific session.

        Args:
            session_id: Target session identifier.
            message: Message to send.

        Returns:
            True if message was sent successfully, False otherwise.
        """
        conn_info = self._connections.get(session_id)
        if not conn_info:
            logger.warning(f"Session not found: {session_id}")
            return False

        try:
            # Encode message
            data = conn_info.protocol.encode(message)

            # Send via WebSocket
            await conn_info.websocket.send_bytes(data)
            conn_info.update_activity()

            return True

        except Exception as e:
            logger.error(f"Error sending message to {session_id}: {e}")
            # Don't disconnect here - let caller handle
            return False

    async def broadcast(
        self, message: Message, exclude: Optional[Set[str]] = None
    ) -> int:
        """Broadcast a message to all connected sessions.

        Args:
            message: Message to broadcast.
            exclude: Optional set of session IDs to exclude.

        Returns:
            Number of sessions the message was sent to.
        """
        exclude = exclude or set()
        sent_count = 0

        async with self._lock:
            for session_id, conn_info in list(self._connections.items()):
                if session_id in exclude:
                    continue

                try:
                    data = conn_info.protocol.encode(message)
                    await conn_info.websocket.send_bytes(data)
                    conn_info.update_activity()
                    sent_count += 1

                except Exception as e:
                    logger.error(f"Error broadcasting to {session_id}: {e}")

        return sent_count

    async def receive_message(self, session_id: str) -> Optional[Message]:
        """Receive and decode a message from a session.

        Args:
            session_id: Session identifier.

        Returns:
            Decoded message, or None if connection was closed.

        Raises:
            ValueError: If message cannot be decoded.
        """
        conn_info = self._connections.get(session_id)
        if not conn_info:
            logger.warning(f"Session not found: {session_id}")
            return None

        try:
            # Receive raw bytes
            data = await conn_info.websocket.receive_bytes()
            conn_info.update_activity()

            # Decode message
            message = conn_info.protocol.decode(data)
            return message

        except Exception as e:
            # Check if it's a normal disconnect
            if isinstance(e, TypeError) and "bytes" in str(e):
                # Might be text/json instead of bytes
                try:
                    data = await conn_info.websocket.receive_text()
                    conn_info.update_activity()
                    message = conn_info.protocol.decode(data.encode())
                    return message
                except Exception:
                    pass

            logger.debug(f"Connection closed or error for {session_id}: {e}")
            return None

    def is_connected(self, session_id: str) -> bool:
        """Check if a session is currently connected.

        Args:
            session_id: Session identifier.

        Returns:
            True if session is connected, False otherwise.
        """
        return session_id in self._connections

    def get_connection(self, session_id: str) -> Optional[ConnectionInfo]:
        """Get connection info for a session.

        Args:
            session_id: Session identifier.

        Returns:
            ConnectionInfo if session exists, None otherwise.
        """
        return self._connections.get(session_id)

    def get_active_sessions(self) -> Set[str]:
        """Get all currently active session IDs.

        Returns:
            Set of active session IDs.
        """
        return set(self._connections.keys())

    async def cleanup_idle_sessions(
        self, idle_timeout_seconds: int
    ) -> Set[str]:
        """Disconnect sessions that have been idle too long.

        Args:
            idle_timeout_seconds: Maximum idle time in seconds.

        Returns:
            Set of session IDs that were cleaned up.
        """
        cleaned = set()
        current_time = asyncio.get_event_loop().time()

        async with self._lock:
            for session_id, conn_info in list(self._connections.items()):
                idle_time = current_time - conn_info.last_activity

                if idle_time > idle_timeout_seconds:
                    logger.info(
                        f"Cleaning up idle session: {session_id}, "
                        f"idle={idle_time:.1f}s"
                    )

                    try:
                        await conn_info.websocket.close(
                            code=1001, reason="Idle timeout"
                        )
                    except Exception:
                        pass

                    del self._connections[session_id]
                    if session_id in self._session_to_websocket:
                        del self._session_to_websocket[session_id]

                    cleaned.add(session_id)

        return cleaned

    async def drain_all(self) -> int:
        """Wait for all active connections to gracefully close.

        Returns:
            Number of connections that were drained.
        """
        count = len(self._connections)

        logger.info(f"Draining {count} WebSocket connections...")

        # Send close signals to all connections
        for session_id, conn_info in list(self._connections.items()):
            try:
                await conn_info.websocket.close(
                    code=1001, reason="Server shutting down"
                )
            except Exception:
                pass

        # Wait a bit for graceful shutdown
        await asyncio.sleep(0.5)

        # Clear all connections
        async with self._lock:
            self._connections.clear()
            self._session_to_websocket.clear()

        logger.info(f"Drained {count} WebSocket connections")
        return count

    @property
    def connection_count(self) -> int:
        """Get the current number of active connections."""
        return len(self._connections)


# Global connection manager instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance.

    Returns:
        The ConnectionManager instance.

    Raises:
        RuntimeError: If connection manager has not been initialized.
    """
    global _connection_manager
    if _connection_manager is None:
        raise RuntimeError("Connection manager not initialized")
    return _connection_manager


def set_connection_manager(manager: ConnectionManager) -> None:
    """Set the global connection manager instance.

    Args:
        manager: The ConnectionManager instance to set.
    """
    global _connection_manager
    _connection_manager = manager
