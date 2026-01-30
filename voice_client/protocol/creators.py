"""Convenience functions for creating messages."""

from voice_client.constants import DEFAULT_CHANNELS, DEFAULT_SAMPLE_RATE
from voice_client.protocol.messages import (
    AudioMessage,
    ConfigMessage,
    EOSMessage,
    TextMessage,
)
from voice_client.protocol.types import MessageType


def create_audio_message(
    data: bytes,
    session_id: str,
    format: str = "pcm_int16",
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    channels: int = DEFAULT_CHANNELS,
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
