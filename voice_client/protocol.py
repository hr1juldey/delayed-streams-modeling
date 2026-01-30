"""
WebSocket protocol implementation for the voice client SDK.

Defines message types, encoders, and convenience functions for
WebSocket communication with the voice server.
"""

import base64
import binascii
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import msgpack

from voice_client.exceptions import ProtocolError


class MessageType(str, Enum):
    """WebSocket message types."""

    AUDIO = "Audio"
    TEXT = "Text"
    ERROR = "Error"
    EOS = "Eos"
    CONFIG = "Config"
    HEARTBEAT = "Heartbeat"


@dataclass
class Message:
    """Base message class for all WebSocket messages.

    Attributes:
        type: The message type from MessageType enum
        data: The message payload (varies by message type)
        session_id: Unique session identifier
        timestamp: Unix timestamp (auto-generated if None)
        metadata: Optional additional metadata
    """

    type: MessageType
    data: Any
    session_id: str = ""
    timestamp: float | None = None
    metadata: dict | None = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class AudioMessage(Message):
    """Message type for audio data.

    Attributes:
        format: Audio format (default: "pcm_int16")
        sample_rate: Sample rate in Hz (default: 24000)
        channels: Number of audio channels (default: 1)
    """

    format: str = "pcm_int16"
    sample_rate: int = 24000
    channels: int = 1


@dataclass
class TextMessage(Message):
    """Message type for text data.

    Attributes:
        is_partial: Whether this is a partial/streaming result
        is_final: Whether this is the final result in a sequence
        confidence: Confidence score for the result
    """

    is_partial: bool = False
    is_final: bool = False
    confidence: float | None = None


@dataclass
class ErrorMessage(Message):
    """Message type for error responses.

    Attributes:
        code: Error code for programmatic handling
        details: Detailed error information
    """

    code: str = "ERROR"
    details: str | None = None


@dataclass
class EOSMessage(Message):
    """Message type for end-of-stream markers.

    Attributes:
        reason: Optional reason for ending the stream
    """

    reason: str | None = None


@dataclass
class ConfigMessage(Message):
    """Message type for configuration.

    Provides a convenience method for accessing configuration values.
    """

    data: dict = field(default_factory=dict)

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            The configuration value or default
        """
        return self.data.get(key, default)


class JSONEncoder:
    """JSON encoder/decoder for WebSocket messages.

    Automatically base64-encodes audio data for JSON compatibility.
    """

    def encode(self, msg: Message) -> bytes:
        """Encode a message to JSON bytes.

        Args:
            msg: The message to encode

        Returns:
            JSON-encoded bytes

        Raises:
            ProtocolError: If encoding fails
        """
        try:
            data = self._message_to_dict(msg)

            # Base64 encode audio data for JSON
            if msg.type == MessageType.AUDIO and isinstance(data.get("data"), bytes):
                data["data"] = base64.b64encode(data["data"]).decode("ascii")

            return json.dumps(data).encode("utf-8")
        except (TypeError, ValueError) as e:
            raise ProtocolError(f"Failed to encode message: {e}") from e

    def decode(self, data: bytes) -> Message:
        """Decode JSON bytes to a message.

        Args:
            data: JSON-encoded bytes

        Returns:
            The decoded message

        Raises:
            ProtocolError: If decoding fails
        """
        try:
            decoded = json.loads(data.decode("utf-8"))

            # Convert type string to enum
            if "type" in decoded and isinstance(decoded["type"], str):
                try:
                    decoded["type"] = MessageType(decoded["type"])
                except ValueError as err:
                    raise ProtocolError(f"Unknown message type: {decoded['type']}") from err

            # Base64 decode audio data
            if decoded.get("type") == MessageType.AUDIO and isinstance(decoded.get("data"), str):
                decoded["data"] = base64.b64decode(decoded["data"])

            return self._create_message(decoded)
        except (json.JSONDecodeError, ValueError, binascii.Error) as e:
            raise ProtocolError(f"Failed to decode message: {e}") from e

    def _message_to_dict(self, msg: Message) -> dict:
        """Convert a message to a dictionary.

        Args:
            msg: The message to convert

        Returns:
            Dictionary representation of the message
        """
        data = {
            "type": msg.type.value if isinstance(msg.type, MessageType) else msg.type,
            "data": msg.data,
            "session_id": msg.session_id,
        }
        if msg.timestamp is not None:
            data["timestamp"] = msg.timestamp
        if msg.metadata:
            data["metadata"] = msg.metadata
        return data

    def _create_message(self, data: dict) -> Message:
        """Create a message from a dictionary.

        Args:
            data: Dictionary with message data

        Returns:
            The appropriate message subclass instance
        """
        msg_type = data.get("type")
        if msg_type == MessageType.AUDIO:
            return AudioMessage(**data)
        elif msg_type == MessageType.TEXT:
            return TextMessage(**data)
        elif msg_type == MessageType.ERROR:
            return ErrorMessage(**data)
        elif msg_type == MessageType.EOS:
            return EOSMessage(**data)
        elif msg_type == MessageType.CONFIG:
            return ConfigMessage(**data)
        else:
            return Message(**data)


class MessagePackEncoder:
    """MessagePack encoder/decoder for WebSocket messages.

    Preserves binary audio data without base64 encoding.
    """

    def encode(self, msg: Message) -> bytes:
        """Encode a message to MessagePack bytes.

        Args:
            msg: The message to encode

        Returns:
            MessagePack-encoded bytes

        Raises:
            ProtocolError: If encoding fails
        """
        try:
            data = self._message_to_dict(msg)
            return msgpack.packb(data, use_bin_type=True)
        except (TypeError, ValueError) as e:
            raise ProtocolError(f"Failed to encode message: {e}") from e

    def decode(self, data: bytes) -> Message:
        """Decode MessagePack bytes to a message.

        Args:
            data: MessagePack-encoded bytes

        Returns:
            The decoded message

        Raises:
            ProtocolError: If decoding fails
        """
        try:
            decoded = msgpack.unpackb(data, raw=False)

            # Convert type string to enum
            if "type" in decoded and isinstance(decoded["type"], str):
                try:
                    decoded["type"] = MessageType(decoded["type"])
                except ValueError as err:
                    raise ProtocolError(f"Unknown message type: {decoded['type']}") from err

            return self._create_message(decoded)
        except (msgpack.exceptions.ExtraData, msgpack.exceptions.UnpackException) as e:
            raise ProtocolError(f"Failed to decode message: {e}") from e

    def _message_to_dict(self, msg: Message) -> dict:
        """Convert a message to a dictionary.

        Args:
            msg: The message to convert

        Returns:
            Dictionary representation of the message
        """
        data = {
            "type": msg.type.value if isinstance(msg.type, MessageType) else msg.type,
            "data": msg.data,
            "session_id": msg.session_id,
        }
        if msg.timestamp is not None:
            data["timestamp"] = msg.timestamp
        if msg.metadata:
            data["metadata"] = msg.metadata
        return data

    def _create_message(self, data: dict) -> Message:
        """Create a message from a dictionary.

        Args:
            data: Dictionary with message data

        Returns:
            The appropriate message subclass instance
        """
        msg_type = data.get("type")
        if msg_type == MessageType.AUDIO:
            return AudioMessage(**data)
        elif msg_type == MessageType.TEXT:
            return TextMessage(**data)
        elif msg_type == MessageType.ERROR:
            return ErrorMessage(**data)
        elif msg_type == MessageType.EOS:
            return EOSMessage(**data)
        elif msg_type == MessageType.CONFIG:
            return ConfigMessage(**data)
        else:
            return Message(**data)


def get_encoder(encoding: str) -> JSONEncoder | MessagePackEncoder:
    """Get an encoder instance for the specified encoding.

    Args:
        encoding: Either "json" or "msgpack"

    Returns:
        An encoder instance

    Raises:
        ValueError: If encoding is not supported
    """
    encoders = {
        "json": JSONEncoder,
        "msgpack": MessagePackEncoder,
    }
    if encoding not in encoders:
        raise ValueError(f"Unsupported encoding: {encoding}. Use 'json' or 'msgpack'.")
    return encoders[encoding]()


# Convenience message constructors


def create_audio_message(
    data: bytes,
    session_id: str,
    format: str = "pcm_int16",
    sample_rate: int = 24000,
    channels: int = 1,
    timestamp: float | None = None,
    metadata: dict | None = None,
) -> AudioMessage:
    """Create an audio message.

    Args:
        data: Raw audio bytes
        session_id: Session identifier
        format: Audio format (default: "pcm_int16")
        sample_rate: Sample rate in Hz (default: 24000)
        channels: Number of channels (default: 1)
        timestamp: Optional timestamp (auto-generated if None)
        metadata: Optional metadata

    Returns:
        An AudioMessage instance
    """
    return AudioMessage(
        type=MessageType.AUDIO,
        data=data,
        session_id=session_id,
        format=format,
        sample_rate=sample_rate,
        channels=channels,
        timestamp=timestamp,
        metadata=metadata,
    )


def create_text_message(
    data: str,
    session_id: str,
    is_partial: bool = False,
    is_final: bool = False,
    confidence: float | None = None,
    timestamp: float | None = None,
    metadata: dict | None = None,
) -> TextMessage:
    """Create a text message.

    Args:
        data: Text content
        session_id: Session identifier
        is_partial: Whether this is a partial result
        is_final: Whether this is the final result
        confidence: Optional confidence score
        timestamp: Optional timestamp (auto-generated if None)
        metadata: Optional metadata

    Returns:
        A TextMessage instance
    """
    return TextMessage(
        type=MessageType.TEXT,
        data=data,
        session_id=session_id,
        is_partial=is_partial,
        is_final=is_final,
        confidence=confidence,
        timestamp=timestamp,
        metadata=metadata,
    )


def create_config_message(
    data: dict,
    session_id: str,
    timestamp: float | None = None,
    metadata: dict | None = None,
) -> ConfigMessage:
    """Create a configuration message.

    Args:
        data: Configuration dictionary
        session_id: Session identifier
        timestamp: Optional timestamp (auto-generated if None)
        metadata: Optional metadata

    Returns:
        A ConfigMessage instance
    """
    return ConfigMessage(
        type=MessageType.CONFIG,
        data=data,
        session_id=session_id,
        timestamp=timestamp,
        metadata=metadata,
    )


def create_eos_message(
    session_id: str,
    reason: str | None = None,
    timestamp: float | None = None,
    metadata: dict | None = None,
) -> EOSMessage:
    """Create an end-of-stream message.

    Args:
        session_id: Session identifier
        reason: Optional reason for ending the stream
        timestamp: Optional timestamp (auto-generated if None)
        metadata: Optional metadata

    Returns:
        An EOSMessage instance
    """
    return EOSMessage(
        type=MessageType.EOS,
        data=None,
        session_id=session_id,
        reason=reason,
        timestamp=timestamp,
        metadata=metadata,
    )
