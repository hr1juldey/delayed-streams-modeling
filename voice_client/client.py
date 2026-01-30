"""
Base WebSocket client with auto-reconnection and protocol handling.

Provides the foundation for STT and TTS clients with connection management,
message encoding/decoding, and automatic reconnection.
"""

import asyncio
import types
import uuid
from collections.abc import Callable
from typing import Any

import websockets
from typing_extensions import Self

from voice_client.exceptions import ConnectionError as VoiceConnectionError
from voice_client.protocol import Message, MessageType, get_encoder


class BaseClient:
    """Base WebSocket client with auto-reconnection and protocol handling.

    Attributes:
        DEFAULT_URL: Default WebSocket URL
        DEFAULT_TIMEOUT: Default connection timeout in seconds
        RECONNECT_INITIAL_DELAY: Initial reconnection delay in seconds
        RECONNECT_MAX_DELAY: Maximum reconnection delay in seconds
        HEARTBEAT_INTERVAL: Heartbeat interval in seconds
    """

    DEFAULT_URL = "ws://localhost:16000/api/v1/ws"
    DEFAULT_TIMEOUT = 30.0
    RECONNECT_INITIAL_DELAY = 1.0
    RECONNECT_MAX_DELAY = 30.0
    HEARTBEAT_INTERVAL = 60.0

    # Subclasses should define this
    endpoint: str = ""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        encoding: str = "json",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the base client.

        Args:
            url: WebSocket server URL (without endpoint)
            api_key: Optional API key for authentication
            encoding: Message encoding ("json" or "msgpack")
            timeout: Connection timeout in seconds
        """
        base_url = url or self.DEFAULT_URL
        self.url = f"{base_url}/{self.endpoint}?encoding={encoding}"
        if api_key:
            self.url += f"&api_key={api_key}"

        self.timeout = timeout
        self.encoding = encoding
        self.encoder = get_encoder(encoding)

        self._ws: websockets.WebSocketClientProtocol | None = None
        self._session_id: str | None = None
        self._message_handlers: dict[MessageType, list[Callable[[Message], Any]]] = {}
        self._running = False
        self._message_task: asyncio.Task[None] | None = None

    @property
    def session_id(self) -> str:
        """Get the current session ID, with empty string fallback.

        Returns:
            The session ID or empty string if not connected
        """
        return self._session_id or ""

    async def __aenter__(self) -> Self:
        """Enter the async context manager.

        Returns:
            The connected client instance
        """
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Exit the async context manager.

        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        await self.disconnect()

    async def connect(self) -> None:
        """Connect with automatic retry and exponential backoff.

        Raises:
            VoiceConnectionError: If connection fails after all retries
        """
        delay = self.RECONNECT_INITIAL_DELAY

        while True:
            try:
                self._ws = await asyncio.wait_for(
                    websockets.connect(self.url),
                    timeout=self.timeout,
                )
                self._session_id = str(uuid.uuid4())
                self._running = True

                # Start message handler task
                self._message_task = asyncio.create_task(self._message_loop())

                return

            except (OSError, asyncio.TimeoutError) as e:
                if delay >= self.RECONNECT_MAX_DELAY:
                    raise VoiceConnectionError(f"Failed to connect after {delay:.1f}s delay") from e

                # Wait before retrying
                await asyncio.sleep(delay)
                delay = min(delay * 2, self.RECONNECT_MAX_DELAY)

    async def disconnect(self) -> None:
        """Gracefully disconnect."""
        self._running = False

        if self._message_task:
            try:
                await asyncio.wait_for(self._message_task, timeout=1.0)
            except asyncio.TimeoutError:
                self._message_task.cancel()
            self._message_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        self._session_id = None

    async def send(self, message: Message) -> None:
        """Send a message.

        Args:
            message: The message to send

        Raises:
            VoiceConnectionError: If not connected
        """
        if not self._ws:
            raise VoiceConnectionError("Not connected")

        # Set session_id if not provided
        if message.session_id is None:
            message.session_id = self.session_id

        encoded = self.encoder.encode(message)
        # JSON encoding uses text frames, MessagePack uses binary frames
        if self.encoding == "json":
            await self._ws.send(encoded.decode("utf-8"))
        else:
            await self._ws.send(encoded)

    async def _message_loop(self) -> None:
        """Background task to receive and handle messages."""
        while self._running and self._ws:
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=1.0)
                # Convert text to bytes for decoding if needed
                if isinstance(raw, str):
                    raw = raw.encode("utf-8")
                message = self.encoder.decode(raw)

                # Call registered handlers
                handlers = self._message_handlers.get(message.type, [])
                for handler in handlers:
                    result = handler(message)
                    if asyncio.iscoroutine(result):
                        await result

            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed:
                self._running = False
                break

    def on_message(
        self,
        msg_type: MessageType,
        handler: Callable[[Message], Any],
    ) -> None:
        """Register a message handler.

        Args:
            msg_type: The message type to handle
            handler: The handler function (sync or async)
        """
        if msg_type not in self._message_handlers:
            self._message_handlers[msg_type] = []
        self._message_handlers[msg_type].append(handler)
