"""WebSocket protocol for voice client communication."""

from voice_client.protocol.common import create_message, message_to_dict
from voice_client.protocol.creators import (
    create_audio_message,
    create_config_message,
    create_eos_message,
    create_text_message,
)
from voice_client.protocol.json_encoder import JSONEncoder
from voice_client.protocol.messages import (
    AudioMessage,
    ConfigMessage,
    EOSMessage,
    ErrorMessage,
    Message,
    TextMessage,
)
from voice_client.protocol.msgpack_encoder import MessagePackEncoder
from voice_client.protocol.types import MessageType

__all__ = [
    "AudioMessage",
    "ConfigMessage",
    "EOSMessage",
    "ErrorMessage",
    "JSONEncoder",
    "Message",
    "MessagePackEncoder",
    "MessageType",
    "TextMessage",
    "create_audio_message",
    "create_config_message",
    "create_eos_message",
    "create_message",
    "create_text_message",
    "get_encoder",
    "message_to_dict",
]

# Encoder factory
_encoders = {
    "json": JSONEncoder,
    "msgpack": MessagePackEncoder,
}


def get_encoder(encoding: str) -> JSONEncoder | MessagePackEncoder:
    """Get an encoder instance for the specified encoding.

    Args:
        encoding: Either "json" or "msgpack"

    Returns:
        An encoder instance

    Raises:
        ValueError: If encoding is not supported
    """
    if encoding not in _encoders:
        raise ValueError(
            f"Unsupported encoding: {encoding}. Use 'json' or 'msgpack'."
        )
    return _encoders[encoding]()
