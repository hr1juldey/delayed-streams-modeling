"""TTS WebSocket endpoint for streaming text-to-speech.

Handles WebSocket connections for real-time speech synthesis
using the Pocket TTS model.
"""

import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from voice_server.config.logging_config import get_logger
from voice_server.config.settings import ServerSettings
from voice_server.src.api.dependencies import get_websocket_auth
from voice_server.src.core.exceptions import AuthenticationException
from voice_server.src.models.tts.model_manager import get_tts_model_manager
from voice_server.src.services.websocket.connection import ConnectionManager
from voice_server.src.services.websocket.protocol import (
    Message,
    MessageType,
    MessageProtocol,
    AudioMessage,
    ErrorMessage,
    EOSMessage,
    ConfigMessage,
)

logger = get_logger(__name__)

router = APIRouter()


class TTSWebSocketHandler:
    """Handler for TTS WebSocket connections."""

    def __init__(
        self,
        websocket: WebSocket,
        session_id: str,
        settings: ServerSettings,
        connection_manager: ConnectionManager,
        protocol: MessageProtocol,
    ):
        """Initialize the TTS WebSocket handler.

        Args:
            websocket: The WebSocket connection.
            session_id: Unique session identifier.
            settings: Server settings.
            connection_manager: Connection manager instance.
            protocol: Message protocol instance.
        """
        self.websocket = websocket
        self.session_id = session_id
        self.settings = settings
        self.connection_manager = connection_manager
        self.protocol = protocol

        # Session state
        self._config: dict = {}
        self._running = False

    async def handle(self) -> None:
        """Main handler for the WebSocket connection."""
        try:
            # Get TTS model manager
            tts_manager = await get_tts_model_manager(self.settings.tts)

            self._running = True
            logger.info(f"TTS WebSocket handler started: {self.session_id}")

            # Message loop
            while self._running:
                try:
                    # Receive message with timeout
                    message = await asyncio.wait_for(
                        self.connection_manager.receive_message(self.session_id),
                        timeout=60.0,
                    )

                    if message is None:
                        logger.info(f"Client disconnected: {self.session_id}")
                        break

                    # Handle message by type
                    await self._handle_message(message, tts_manager)

                except asyncio.TimeoutError:
                    # Send heartbeat/ping
                    heartbeat = Message(
                        type=MessageType.HEARTBEAT,
                        data={"ping": asyncio.get_event_loop().time()},
                        session_id=self.session_id,
                    )
                    await self.connection_manager.send_message(self.session_id, heartbeat)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {self.session_id}")
        except Exception as e:
            logger.error(f"Error in TTS handler: {e}")
            await self._send_error(str(e))
        finally:
            await self._cleanup()

    async def _handle_message(self, message: Message, tts_manager) -> None:
        """Handle an incoming message.

        Args:
            message: The message to handle.
            tts_manager: TTS model manager.
        """
        if message.type == MessageType.CONFIG:
            await self._handle_config(message)
        elif message.type == MessageType.TEXT:
            await self._handle_text(message, tts_manager)
        elif message.type == MessageType.EOS:
            # Acknowledge EOS
            eos_ack = EOSMessage(
                type=MessageType.EOS,
                data=None,
                session_id=self.session_id,
                reason=message.reason,
            )
            await self.connection_manager.send_message(self.session_id, eos_ack)
            self._running = False
        elif message.type == MessageType.HEARTBEAT:
            # Respond to heartbeat
            await self.connection_manager.send_message(
                self.session_id,
                Message(
                    type=MessageType.HEARTBEAT,
                    data={"pong": asyncio.get_event_loop().time()},
                    session_id=self.session_id,
                ),
            )
        else:
            logger.warning(f"Unhandled message type: {message.type}")

    async def _handle_config(self, message: ConfigMessage) -> None:
        """Handle configuration message.

        Args:
            message: Config message.
        """
        if isinstance(message.data, dict):
            self._config.update(message.data)
            logger.debug(f"Updated config for {self.session_id}: {self._config}")

        # Acknowledge config
        ack = Message(
            type=MessageType.CONFIG,
            data={"status": "configured"},
            session_id=self.session_id,
        )
        await self.connection_manager.send_message(self.session_id, ack)

    async def _handle_text(self, message: Message, tts_manager) -> None:
        """Handle text message for synthesis.

        Args:
            message: Text message.
            tts_manager: TTS model manager.
        """
        try:
            # Get text data
            if isinstance(message.data, str):
                text = message.data
            elif isinstance(message.data, dict) and "text" in message.data:
                text = message.data["text"]
            else:
                logger.error(f"Invalid text data type: {type(message.data)}")
                await self._send_error("Invalid text data format")
                return

            if not text:
                await self._send_error("Empty text")
                return

            # Get synthesis parameters
            voice_id = self._config.get("voice_id", self.settings.tts.default_voice)
            output_format = self._config.get("output_format", "pcm_int16")
            streaming = self._config.get("streaming", True)

            logger.info(f"Synthesizing text for {self.session_id}: {len(text)} chars")

            # Synthesize
            if streaming:
                await self._synthesize_stream(text, voice_id, output_format, tts_manager)
            else:
                await self._synthesize_complete(text, voice_id, output_format, tts_manager)

        except Exception as e:
            logger.error(f"Error synthesizing text: {e}")
            await self._send_error(f"Synthesis error: {e}")

    async def _synthesize_stream(
        self,
        text: str,
        voice_id: str,
        output_format: str,
        tts_manager,
    ) -> None:
        """Synthesize speech with streaming output.

        Args:
            text: Text to synthesize.
            voice_id: Voice identifier.
            output_format: Audio output format.
            tts_manager: TTS model manager.
        """
        async for chunk in tts_manager.synthesize_stream(
            text=text,
            voice_id=voice_id,
            output_format=output_format,
            session_id=self.session_id,
        ):
            # Send audio chunk
            audio_msg = AudioMessage(
                type=MessageType.AUDIO,
                data=chunk.audio,
                session_id=self.session_id,
                format=output_format,
                sample_rate=self.settings.audio.output_sample_rate,
                channels=1,
            )
            await self.connection_manager.send_message(self.session_id, audio_msg)

            if chunk.is_final:
                break

        # Send EOS marker
        eos_msg = EOSMessage(
            type=MessageType.EOS,
            data=None,
            session_id=self.session_id,
            reason="synthesis_complete",
        )
        await self.connection_manager.send_message(self.session_id, eos_msg)

    async def _synthesize_complete(
        self,
        text: str,
        voice_id: str,
        output_format: str,
        tts_manager,
    ) -> None:
        """Synthesize speech and send complete result.

        Args:
            text: Text to synthesize.
            voice_id: Voice identifier.
            output_format: Audio output format.
            tts_manager: TTS model manager.
        """
        result = await tts_manager.synthesize(
            text=text,
            voice_id=voice_id,
            output_format=output_format,
            session_id=self.session_id,
        )

        # Send complete audio
        audio_msg = AudioMessage(
            type=MessageType.AUDIO,
            data=result.audio,
            session_id=self.session_id,
            format=output_format,
            sample_rate=result.sample_rate,
            channels=1,
        )
        await self.connection_manager.send_message(self.session_id, audio_msg)

        # Send EOS marker
        eos_msg = EOSMessage(
            type=MessageType.EOS,
            data=None,
            session_id=self.session_id,
            reason="synthesis_complete",
        )
        await self.connection_manager.send_message(self.session_id, eos_msg)

    async def _send_error(self, message: str, code: str = "TTS_ERROR") -> None:
        """Send an error message to the client.

        Args:
            message: Error message.
            code: Error code.
        """
        error_msg = ErrorMessage(
            type=MessageType.ERROR,
            data={"message": message},
            session_id=self.session_id,
            code=code,
        )
        await self.connection_manager.send_message(self.session_id, error_msg)

    async def _cleanup(self) -> None:
        """Clean up resources."""
        self._running = False
        logger.info(f"TTS WebSocket handler cleanup complete: {self.session_id}")


@router.websocket("/api/v1/ws/tts")
async def tts_websocket(websocket: WebSocket):
    """TTS WebSocket endpoint for streaming text-to-speech.

    Accepts WebSocket connections and streams synthesized speech audio.

    Message Flow:
    1. Client connects (with optional API key)
    2. Client sends Config message (optional, sets voice, output format, etc.)
    3. Client sends Text messages (text to synthesize)
    4. Server sends Audio messages (synthesized audio chunks)
    5. Server sends EOS message when synthesis complete

    Authentication:
    - API key via query parameter: ?api_key=YOUR_KEY
    - API key via header: Authorization: Bearer YOUR_KEY

    Audio Format:
    - Default: PCM int16, 24kHz, mono
    - Configurable via Config message (int16, float32, wav)

    Message Encoding:
    - Default: JSON
    - Configurable via msgpack query parameter: ?encoding=msgpack
    """
    # Get settings
    settings = ServerSettings()

    # Authenticate
    try:
        await get_websocket_auth(websocket)
    except (AuthenticationException, ValueError) as e:
        logger.warning(f"TTS WebSocket authentication failed: {e}")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason=str(e)
        )
        return

    # Generate session ID
    session_id = str(uuid.uuid4())

    # Get encoding preference
    encoding = websocket.query_params.get("encoding", "json")

    # Get connection manager
    from src.services.websocket.connection import get_connection_manager

    try:
        connection_manager = get_connection_manager()
    except RuntimeError:
        # Connection manager not initialized - create temporary one
        from src.services.websocket.connection import ConnectionManager

        connection_manager = ConnectionManager(settings)

    # Accept connection
    protocol = MessageProtocol(encoding=encoding)

    try:
        conn_info = await connection_manager.connect(websocket, session_id, encoding)
    except (RuntimeError, ValueError) as e:
        logger.warning(f"Failed to accept TTS WebSocket: {e}")
        return

    logger.info(f"TTS WebSocket connected: {session_id}")

    # Create handler and run
    handler = TTSWebSocketHandler(
        websocket, session_id, settings, connection_manager, protocol
    )

    try:
        await handler.handle()
    except Exception as e:
        logger.error(f"TTS WebSocket handler error: {e}")
    finally:
        await connection_manager.disconnect(session_id)
        logger.info(f"TTS WebSocket disconnected: {session_id}")
