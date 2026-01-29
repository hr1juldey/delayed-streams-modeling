"""WebSocket message protocol for bidirectional streaming.

Supports both JSON and MessagePack encoding for efficient message transmission.
"""

import json
import msgpack
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any

from config.logging_config import get_logger

logger = get_logger(__name__)


class MessageType(str, Enum):
    """Message types for WebSocket communication."""

    AUDIO = "Audio"
    TEXT = "Text"
    ERROR = "Error"
    EOS = "Eos"
    CONFIG = "Config"
    HEARTBEAT = "Heartbeat"


@dataclass
class Message:
    """Base message structure for WebSocket communication.

    Attributes:
        type: The message type from MessageType enum.
        data: The message payload (varies by type).
        session_id: Unique identifier for the session.
        timestamp: Unix timestamp when message was created.
        metadata: Optional additional metadata.
    """

    type: MessageType
    data: Any
    session_id: str
    timestamp: float = None
    metadata: dict | None = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class AudioMessage(Message):
    """Audio data message.

    The data field contains audio bytes or array data.
    Additional metadata may include format, sample rate, etc.
    """

    format: str = "pcm_int16"  # pcm_int16, pcm_float32, wav
    sample_rate: int = 24000
    channels: int = 1


@dataclass
class TextMessage(Message):
    """Text data message for STT results or TTS input.

    Attributes:
        is_partial: Whether this is partial (streaming) or final result.
        is_final: Whether this is the final result in a sequence.
    """

    is_partial: bool = False
    is_final: bool = False
    confidence: float | None = None


@dataclass
class ErrorMessage(Message):
    """Error message.

    Attributes:
        code: Error code for programmatic handling.
        details: Detailed error information.
    """

    code: str = "ERROR"
    details: str | None = None


@dataclass
class EOSMessage(Message):
    """End of Stream marker message.

    Indicates that no more data will be sent for this session.
    """

    reason: str | None = None


@dataclass
class ConfigMessage(Message):
    """Configuration message for setting session parameters.

    The data field contains a dict of configuration options.
    """

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: Configuration key.
            default: Default value if key not found.

        Returns:
            The configuration value or default.
        """
        if isinstance(self.data, dict):
            return self.data.get(key, default)
        return default


class MessageProtocol:
    """Protocol for encoding/decoding WebSocket messages.

    Supports both JSON (human-readable, debuggable) and MessagePack
    (binary, more efficient) encoding formats.
    """

    def __init__(self, encoding: str = "json"):
        """Initialize the protocol.

        Args:
            encoding: Either "json" or "msgpack".
        """
        if encoding not in ("json", "msgpack"):
            raise ValueError(f"Unsupported encoding: {encoding}")
        self.encoding = encoding

    def encode(self, msg: Message) -> bytes:
        """Encode a message to bytes.

        Args:
            msg: The message to encode.

        Returns:
            Encoded message as bytes.
        """
        try:
            # Convert to dict, handling MessageType enum
            data = asdict(msg)
            data["type"] = msg.type.value  # Convert enum to string

            if self.encoding == "msgpack":
                return msgpack.packb(data, use_bin_type=True)
            else:
                return json.dumps(data).encode("utf-8")

        except Exception as e:
            logger.error(f"Error encoding message: {e}")
            # Return error message
            error_msg = ErrorMessage(
                type=MessageType.ERROR,
                data={"message": "Encoding error"},
                session_id=getattr(msg, "session_id", "unknown"),
                code="ENCODING_ERROR",
            )
            if self.encoding == "msgpack":
                return msgpack.packb(asdict(error_msg), use_bin_type=True)
            return json.dumps(asdict(error_msg)).encode("utf-8")

    def decode(self, data: bytes) -> Message:
        """Decode bytes to a message.

        Args:
            data: The encoded message bytes.

        Returns:
            Decoded Message object.

        Raises:
            ValueError: If data is invalid or cannot be decoded.
        """
        try:
            if self.encoding == "msgpack":
                decoded = msgpack.unpackb(data, raw=False)
            else:
                decoded = json.loads(data.decode("utf-8"))

            # Convert type string back to enum
            msg_type = decoded.get("type")
            if msg_type:
                try:
                    decoded["type"] = MessageType(msg_type)
                except ValueError:
                    logger.warning(f"Unknown message type: {msg_type}")
                    decoded["type"] = MessageType.ERROR

            # Create appropriate message subclass based on type
            msg_type = decoded["type"]

            if msg_type == MessageType.AUDIO:
                return AudioMessage(**decoded)
            elif msg_type == MessageType.TEXT:
                return TextMessage(**decoded)
            elif msg_type == MessageType.ERROR:
                return ErrorMessage(**decoded)
            elif msg_type == MessageType.EOS:
                return EOSMessage(**decoded)
            elif msg_type == MessageType.CONFIG:
                return ConfigMessage(**decoded)
            else:
                return Message(**decoded)

        except Exception as e:
            logger.error(f"Error decoding message: {e}")
            raise ValueError(f"Failed to decode message: {e}") from e

    def create_audio_message(
        self,
        data: Any,
        session_id: str,
        format: str = "pcm_int16",
        sample_rate: int = 24000,
        channels: int = 1,
    ) -> AudioMessage:
        """Create an audio message.

        Args:
            data: Audio data (bytes or array).
            session_id: Session identifier.
            format: Audio format (pcm_int16, pcm_float32, wav).
            sample_rate: Sample rate in Hz.
            channels: Number of audio channels.

        Returns:
            AudioMessage instance.
        """
        return AudioMessage(
            type=MessageType.AUDIO,
            data=data,
            session_id=session_id,
            format=format,
            sample_rate=sample_rate,
            channels=channels,
        )

    def create_text_message(
        self,
        data: str,
        session_id: str,
        is_partial: bool = False,
        is_final: bool = False,
        confidence: float | None = None,
    ) -> TextMessage:
        """Create a text message.

        Args:
            data: Text content.
            session_id: Session identifier.
            is_partial: Whether this is a partial result.
            is_final: Whether this is the final result.
            confidence: Optional confidence score.

        Returns:
            TextMessage instance.
        """
        return TextMessage(
            type=MessageType.TEXT,
            data=data,
            session_id=session_id,
            is_partial=is_partial,
            is_final=is_final,
            confidence=confidence,
        )

    def create_error_message(
        self,
        data: str | dict,
        session_id: str,
        code: str = "ERROR",
        details: str | None = None,
    ) -> ErrorMessage:
        """Create an error message.

        Args:
            data: Error message or data.
            session_id: Session identifier.
            code: Error code.
            details: Detailed error information.

        Returns:
            ErrorMessage instance.
        """
        if isinstance(data, str):
            data = {"message": data}

        return ErrorMessage(
            type=MessageType.ERROR,
            data=data,
            session_id=session_id,
            code=code,
            details=details,
        )

    def create_eos_message(
        self, session_id: str, reason: str | None = None
    ) -> EOSMessage:
        """Create an end-of-stream message.

        Args:
            session_id: Session identifier.
            reason: Optional reason for ending stream.

        Returns:
            EOSMessage instance.
        """
        return EOSMessage(
            type=MessageType.EOS,
            data=None,
            session_id=session_id,
            reason=reason,
        )

    def create_config_message(
        self, data: dict, session_id: str
    ) -> ConfigMessage:
        """Create a configuration message.

        Args:
            data: Configuration dictionary.
            session_id: Session identifier.

        Returns:
            ConfigMessage instance.
        """
        return ConfigMessage(
            type=MessageType.CONFIG,
            data=data,
            session_id=session_id,
        )


def get_protocol(encoding: str = "json") -> MessageProtocol:
    """Get a message protocol instance.

    Args:
        encoding: Either "json" or "msgpack".

    Returns:
        MessageProtocol instance.
    """
    return MessageProtocol(encoding=encoding)
