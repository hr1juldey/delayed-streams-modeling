"""Message dataclasses for WebSocket communication."""

import time
from dataclasses import dataclass, field
from typing import Any

from voice_client.protocol.types import MessageType


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
