"""Message type enumeration."""

from enum import Enum


class MessageType(str, Enum):
    """WebSocket message types."""

    AUDIO = "Audio"
    TEXT = "Text"
    ERROR = "Error"
    EOS = "Eos"
    CONFIG = "Config"
    HEARTBEAT = "Heartbeat"
