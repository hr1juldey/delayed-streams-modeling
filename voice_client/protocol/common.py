"""Common message conversion utilities for encoders."""

from voice_client.protocol.messages import (
    AudioMessage,
    ConfigMessage,
    EOSMessage,
    ErrorMessage,
    Message,
    TextMessage,
)
from voice_client.protocol.types import MessageType


def message_to_dict(msg: Message) -> dict:
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


def create_message(data: dict) -> Message:
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
