"""Session routing utilities for WebSocket message distribution.

Provides utilities for routing messages to sessions based on various criteria.
"""

import asyncio
from typing import Optional, Set, Callable, Awaitable, Any
from fastapi import WebSocket

from config.logging_config import get_logger
from src.services.websocket.connection import ConnectionManager, ConnectionInfo
from src.services.websocket.protocol import Message, MessageType

logger = get_logger(__name__)


class MessageRouter:
    """Routes incoming messages to appropriate handlers.

    Provides pattern-based routing, filtering, and handler registration.
    """

    def __init__(self, connection_manager: ConnectionManager):
        """Initialize the message router.

        Args:
            connection_manager: Connection manager for session access.
        """
        self.connection_manager = connection_manager
        self._handlers: dict[MessageType, list[Callable]] = {}
        self._middleware: list[Callable] = []

    def register_handler(
        self,
        message_type: MessageType,
        handler: Callable[[ConnectionInfo, Message], Awaitable[None]],
    ) -> None:
        """Register a handler for a specific message type.

        Args:
            message_type: The message type to handle.
            handler: Async function that takes ConnectionInfo and Message.
        """
        if message_type not in self._handlers:
            self._handlers[message_type] = []
        self._handlers[message_type].append(handler)
        logger.debug(f"Registered handler for {message_type}")

    def register_middleware(
        self,
        middleware: Callable[[ConnectionInfo, Message], Awaitable[Optional[Message]]],
    ) -> None:
        """Register middleware to process messages before handlers.

        Middleware can modify or block messages. Return None from middleware
        to block the message from reaching handlers.

        Args:
            middleware: Async function that takes ConnectionInfo and Message,
                       returns optional modified Message.
        """
        self._middleware.append(middleware)
        logger.debug("Registered message middleware")

    async def route_message(
        self, session_id: str, message: Message
    ) -> None:
        """Route a message to appropriate handlers.

        Args:
            session_id: Source session ID.
            message: The message to route.
        """
        conn_info = self.connection_manager.get_connection(session_id)
        if not conn_info:
            logger.warning(f"Cannot route message: session not found: {session_id}")
            return

        try:
            # Apply middleware
            processed_message = message
            for middleware in self._middleware:
                result = await middleware(conn_info, processed_message)
                if result is None:
                    # Middleware blocked the message
                    logger.debug(f"Message blocked by middleware: {message.type}")
                    return
                processed_message = result

            # Route to handlers
            handlers = self._handlers.get(processed_message.type, [])
            if not handlers:
                logger.debug(f"No handlers for message type: {processed_message.type}")
                return

            # Execute all handlers concurrently
            tasks = [
                handler(conn_info, processed_message) for handler in handlers
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"Error routing message: {e}")


class SessionRouter:
    """Routes messages between sessions and manages broadcast groups.

    Features:
    - Broadcast groups (channels)
    - Session filtering by metadata
    - Targeted message delivery
    """

    def __init__(self, connection_manager: ConnectionManager):
        """Initialize the session router.

        Args:
            connection_manager: Connection manager for session access.
        """
        self.connection_manager = connection_manager
        self._groups: dict[str, Set[str]] = {}
        self._session_metadata: dict[str, dict] = {}

    async def send_to_session(
        self, session_id: str, message: Message
    ) -> bool:
        """Send a message to a specific session.

        Args:
            session_id: Target session ID.
            message: Message to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        return await self.connection_manager.send_message(session_id, message)

    async def broadcast(
        self,
        message: Message,
        group: Optional[str] = None,
        exclude: Optional[Set[str]] = None,
    ) -> int:
        """Broadcast a message to sessions.

        Args:
            message: Message to broadcast.
            group: Optional group name to broadcast to.
            exclude: Optional set of session IDs to exclude.

        Returns:
            Number of sessions message was sent to.
        """
        target_sessions = self._get_target_sessions(group)
        exclude = exclude or set()

        sent_count = 0
        for session_id in target_sessions:
            if session_id in exclude:
                continue

            success = await self.connection_manager.send_message(session_id, message)
            if success:
                sent_count += 1

        return sent_count

    async def broadcast_to_others(
        self, sender_session_id: str, message: Message, group: Optional[str] = None
    ) -> int:
        """Broadcast a message to all sessions except the sender.

        Args:
            sender_session_id: Session ID to exclude.
            message: Message to broadcast.
            group: Optional group name to broadcast to.

        Returns:
            Number of sessions message was sent to.
        """
        return await self.broadcast(message, group=group, exclude={sender_session_id})

    def join_group(self, session_id: str, group: str) -> None:
        """Add a session to a broadcast group.

        Args:
            session_id: Session ID to add.
            group: Group name.
        """
        if group not in self._groups:
            self._groups[group] = set()
        self._groups[group].add(session_id)
        logger.debug(f"Session {session_id} joined group: {group}")

    def leave_group(self, session_id: str, group: str) -> None:
        """Remove a session from a broadcast group.

        Args:
            session_id: Session ID to remove.
            group: Group name.
        """
        if group in self._groups and session_id in self._groups[group]:
            self._groups[group].discard(session_id)
            logger.debug(f"Session {session_id} left group: {group}")

            # Clean up empty groups
            if not self._groups[group]:
                del self._groups[group]

    def leave_all_groups(self, session_id: str) -> None:
        """Remove a session from all groups.

        Args:
            session_id: Session ID to remove.
        """
        for group in list(self._groups.keys()):
            self.leave_group(session_id, group)

    def set_session_metadata(self, session_id: str, metadata: dict) -> None:
        """Set metadata for a session.

        Args:
            session_id: Session ID.
            metadata: Metadata dictionary.
        """
        self._session_metadata[session_id] = metadata

    def get_session_metadata(self, session_id: str) -> dict:
        """Get metadata for a session.

        Args:
            session_id: Session ID.

        Returns:
            Metadata dictionary, or empty dict if not found.
        """
        return self._session_metadata.get(session_id, {})

    def filter_sessions(
        self, predicate: Callable[[str, dict], bool]
    ) -> Set[str]:
        """Filter sessions based on metadata predicate.

        Args:
            predicate: Function that takes session_id and metadata,
                      returns True if session should be included.

        Returns:
            Set of matching session IDs.
        """
        matching = set()
        for session_id, metadata in self._session_metadata.items():
            if predicate(session_id, metadata):
                matching.add(session_id)
        return matching

    def _get_target_sessions(self, group: Optional[str]) -> Set[str]:
        """Get target sessions for a broadcast.

        Args:
            group: Optional group name.

        Returns:
            Set of target session IDs.
        """
        if group:
            return self._groups.get(group, set())
        return self.connection_manager.get_active_sessions()

    def get_group_members(self, group: str) -> Set[str]:
        """Get all members of a group.

        Args:
            group: Group name.

        Returns:
            Set of session IDs in the group.
        """
        return self._groups.get(group, set()).copy()

    def get_all_groups(self) -> Set[str]:
        """Get all active group names.

        Returns:
            Set of group names.
        """
        return set(self._groups.keys())


def create_session_router(connection_manager: ConnectionManager) -> SessionRouter:
    """Create a new session router.

    Args:
        connection_manager: Connection manager for session access.

    Returns:
        SessionRouter instance.
    """
    return SessionRouter(connection_manager)


def create_message_router(connection_manager: ConnectionManager) -> MessageRouter:
    """Create a new message router.

    Args:
        connection_manager: Connection manager for session access.

    Returns:
        MessageRouter instance.
    """
    return MessageRouter(connection_manager)
