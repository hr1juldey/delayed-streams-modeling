"""MessagePack encoder/decoder for WebSocket messages."""

import msgpack

from voice_client.exceptions import ProtocolError
from voice_client.protocol.common import create_message, message_to_dict
from voice_client.protocol.messages import Message
from voice_client.protocol.types import MessageType


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
            data = message_to_dict(msg)
            result: bytes = msgpack.packb(data, use_bin_type=True)  # type: ignore[assignment]
            return result
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
                    raise ProtocolError(
                        f"Unknown message type: {decoded['type']}"
                    ) from err

            return create_message(decoded)
        except (
            msgpack.exceptions.ExtraData,
            msgpack.exceptions.UnpackException,
        ) as e:
            raise ProtocolError(f"Failed to decode message: {e}") from e
