"""JSON encoder/decoder for WebSocket messages."""

import base64
import binascii
import json

from voice_client.exceptions import ProtocolError
from voice_client.protocol.common import create_message, message_to_dict
from voice_client.protocol.messages import Message
from voice_client.protocol.types import MessageType


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
            data = message_to_dict(msg)

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
                    raise ProtocolError(
                        f"Unknown message type: {decoded['type']}"
                    ) from err

            # Base64 decode audio data
            if (
                decoded.get("type") == MessageType.AUDIO
                and isinstance(decoded.get("data"), str)
            ):
                decoded["data"] = base64.b64decode(decoded["data"])

            return create_message(decoded)
        except (json.JSONDecodeError, ValueError, binascii.Error) as e:
            raise ProtocolError(f"Failed to decode message: {e}") from e
