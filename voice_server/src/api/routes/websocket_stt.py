"""STT WebSocket endpoint for streaming speech-to-text.

Handles WebSocket connections for real-time audio transcription
using the Kyutai STT model.
"""

import asyncio
import uuid
from typing import Optional

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from voice_server.config.logging_config import get_logger
from voice_server.config.settings import ServerSettings
from voice_server.src.api.dependencies import get_websocket_auth
from voice_server.src.core.exceptions import AuthenticationException, SessionException
from voice_server.src.models.stt.model_manager import get_stt_model_manager
from voice_server.src.services.websocket.connection import ConnectionManager
from voice_server.src.services.websocket.protocol import (
    Message,
    MessageType,
    MessageProtocol,
    TextMessage,
    ErrorMessage,
    EOSMessage,
    ConfigMessage,
)
from voice_server.src.services.audio.processor import AudioProcessor

logger = get_logger(__name__)

router = APIRouter()


class STTWebSocketHandler:
    """Handler for STT WebSocket connections."""

    def __init__(
        self,
        websocket: WebSocket,
        session_id: str,
        settings: ServerSettings,
        connection_manager: ConnectionManager,
        protocol: MessageProtocol,
    ):
        """Initialize the STT WebSocket handler.

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

        # Processing components
        self.audio_processor = AudioProcessor(settings.audio)

        # Session state
        self._stt_session_id: Optional[str] = None
        self._config: dict = {}
        self._running = False

    async def handle(self) -> None:
        """Main handler for the WebSocket connection."""
        try:
            # Get STT model manager
            stt_manager = await get_stt_model_manager()

            # Start STT stream
            self._stt_session_id = f"stt_{self.session_id}"
            await stt_manager.start_stream(self._stt_session_id)

            self._running = True
            logger.info(f"STT WebSocket handler started: {self.session_id}")

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
                    await self._handle_message(message, stt_manager)

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
            logger.error(f"Error in STT handler: {e}")
            await self._send_error(str(e))
        finally:
            await self._cleanup()

    async def _handle_message(self, message: Message, stt_manager) -> None:
        """Handle an incoming message.

        Args:
            message: The message to handle.
            stt_manager: STT model manager.
        """
        if message.type == MessageType.CONFIG:
            await self._handle_config(message)
        elif message.type == MessageType.AUDIO:
            await self._handle_audio(message, stt_manager)
        elif message.type == MessageType.EOS:
            await self._handle_eos(message, stt_manager)
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

    async def _handle_audio(self, message: Message, stt_manager) -> None:
        """Handle audio message.

        Args:
            message: Audio message.
            stt_manager: STT model manager.
        """
        try:
            # Get audio data - handle both bytes (msgpack) and base64 strings (JSON)
            if isinstance(message.data, bytes):
                audio_bytes = message.data
            elif isinstance(message.data, str):
                # JSON encoding - decode from base64
                import base64
                try:
                    audio_bytes = base64.b64decode(message.data)
                except Exception as e:
                    logger.error(f"Failed to decode base64 audio data: {e}")
                    await self._send_error("Invalid base64 audio data")
                    return
            else:
                logger.error(f"Invalid audio data type: {type(message.data)}")
                await self._send_error("Invalid audio data format")
                return

            # Process audio
            input_format = self._config.get("input_format", "int16")
            audio_array = await self.audio_processor.process_input_chunk(
                audio_bytes, input_format
            )

            # Process through STT
            result = await stt_manager.process_audio(audio_array, self._stt_session_id)

            # Send result if available
            if result:
                streaming_mode = self._config.get("streaming_mode", "both")

                should_send = False
                is_partial = False
                is_final = False

                if streaming_mode == "partial" and result.is_partial:
                    should_send = True
                    is_partial = True
                elif streaming_mode == "final" and result.is_final:
                    should_send = True
                    is_final = True
                elif streaming_mode == "both":
                    should_send = True
                    is_partial = result.is_partial
                    is_final = result.is_final

                if should_send and result.text:
                    text_msg = TextMessage(
                        type=MessageType.TEXT,
                        data=result.text,
                        session_id=self.session_id,
                        is_partial=is_partial,
                        is_final=is_final,
                        confidence=result.confidence,
                    )
                    await self.connection_manager.send_message(self.session_id, text_msg)

                    # Reset partial text after final result
                    if is_final:
                        logger.info(f"Final transcription: {result.text}")

        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            await self._send_error(f"Audio processing error: {e}")

    async def _handle_eos(self, message: EOSMessage, stt_manager) -> None:
        """Handle end-of-stream message.

        Args:
            message: EOS message.
            stt_manager: STT model manager.
        """
        try:
            logger.info(f"EOS received for {self.session_id}, finalizing...")

            # Finalize STT stream
            final_result = await stt_manager.finalize_stream(self._stt_session_id)

            # Send final result
            if final_result.text:
                text_msg = TextMessage(
                    type=MessageType.TEXT,
                    data=final_result.text,
                    session_id=self.session_id,
                    is_partial=False,
                    is_final=True,
                    confidence=final_result.confidence,
                )
                await self.connection_manager.send_message(self.session_id, text_msg)

            # Send EOS acknowledgment
            eos_ack = EOSMessage(
                type=MessageType.EOS,
                data=None,
                session_id=self.session_id,
                reason=message.reason,
            )
            await self.connection_manager.send_message(self.session_id, eos_ack)

            # Stop handler
            self._running = False

        except Exception as e:
            logger.error(f"Error handling EOS: {e}")
            await self._send_error(f"EOS handling error: {e}")

    async def _send_error(self, message: str, code: str = "STT_ERROR") -> None:
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

        # End STT stream
        if self._stt_session_id:
            try:
                stt_manager = await get_stt_model_manager()
                await stt_manager.end_stream(self._stt_session_id)
            except Exception as e:
                logger.error(f"Error ending STT stream: {e}")

        logger.info(f"STT WebSocket handler cleanup complete: {self.session_id}")


@router.websocket("/api/v1/ws/stt")
async def stt_websocket(websocket: WebSocket):
    """STT WebSocket endpoint for streaming speech-to-text.

    Accepts WebSocket connections and streams audio transcription results.

    Message Flow:
    1. Client connects (with optional API key)
    2. Client sends Config message (optional, sets streaming mode, VAD mode, etc.)
    3. Client sends Audio messages (audio chunks)
    4. Server sends Text messages (transcription results)
    5. Client sends EOS message when done
    6. Server sends final Text result and EOS acknowledgment

    Authentication:
    - API key via query parameter: ?api_key=YOUR_KEY
    - API key via header: Authorization: Bearer YOUR_KEY

    Audio Format:
    - Default: PCM int16, 24kHz, mono
    - Configurable via Config message

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
        logger.warning(f"STT WebSocket authentication failed: {e}")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason=str(e)
        )
        return

    # Generate session ID
    session_id = str(uuid.uuid4())

    # Get encoding preference
    encoding = websocket.query_params.get("encoding", "json")

    # Get connection manager
    from voice_server.src.services.websocket.connection import get_connection_manager

    try:
        connection_manager = get_connection_manager()
    except RuntimeError:
        # Connection manager not initialized - create temporary one
        from voice_server.src.services.websocket.connection import ConnectionManager

        connection_manager = ConnectionManager(settings)

    # Accept connection
    try:
        conn_info = await connection_manager.connect(websocket, session_id, encoding)
    except (RuntimeError, ValueError) as e:
        logger.warning(f"Failed to accept STT WebSocket: {e}")
        return

    logger.info(f"STT WebSocket connected: {session_id}")

    # Create handler and run (use protocol from conn_info)
    handler = STTWebSocketHandler(
        websocket, session_id, settings, connection_manager, conn_info.protocol
    )

    try:
        await handler.handle()
    except Exception as e:
        logger.error(f"STT WebSocket handler error: {e}")
    finally:
        await connection_manager.disconnect(session_id)
        logger.info(f"STT WebSocket disconnected: {session_id}")
