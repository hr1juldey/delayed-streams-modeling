"""Text-to-Speech (TTS) client for the voice server."""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from voice_client.audio import AudioHandler
from voice_client.client import BaseClient
from voice_client.constants import DEFAULT_SAMPLE_RATE
from voice_client.exceptions import ConfigurationError
from voice_client.exceptions import ServerError as VoiceServerError
from voice_client.protocol import (
    AudioMessage,
    EOSMessage,
    Message,
    MessageType,
    TextMessage,
    create_config_message,
    create_text_message,
)
from voice_client.tts.chunk import AudioChunk


class TTSClient(BaseClient):
    """Text-to-Speech client with streaming audio output.

    Attributes:
        endpoint: WebSocket endpoint for TTS
    """

    endpoint = "tts"

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the TTS client.

        Args:
            url: WebSocket server URL
            api_key: Optional API key for authentication
            config: Optional configuration for TTS
            **kwargs: Additional arguments passed to BaseClient
        """
        super().__init__(url, api_key, **kwargs)
        self.config = {
            "voice_id": "default",
            "output_format": "pcm_int16",
            "streaming": True,
            **(config or {}),
        }
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._eos_event = asyncio.Event()

    async def configure(self) -> None:
        """Send configuration to the server."""
        await self.send(
            create_config_message(
                data=self.config,
                session_id=self.session_id,
            )
        )

    async def synthesize(self, text: str) -> AsyncIterator[AudioChunk]:
        """Synthesize speech from text.

        Args:
            text: Text to synthesize

        Yields:
            AudioChunk with audio data

        Raises:
            ConfigurationError: If text is empty
            VoiceServerError: If synthesis fails
        """
        if not text or not text.strip():
            raise ConfigurationError("Text cannot be empty")

        # Register handlers
        async def audio_handler(msg: Message) -> None:
            if isinstance(msg, AudioMessage):
                await self._audio_queue.put(msg.data)

        async def eos_handler(msg: Message) -> None:
            if isinstance(msg, EOSMessage):
                self._eos_event.set()

        async def error_handler(msg: Message) -> None:
            if isinstance(msg, TextMessage) and msg.type == MessageType.ERROR:
                error = VoiceServerError(
                    str(msg.data),
                    code=getattr(msg, "code", "ERROR"),
                    details=getattr(msg, "details", None),
                )
                raise error

        self.on_message(MessageType.AUDIO, audio_handler)
        self.on_message(MessageType.EOS, eos_handler)
        self.on_message(MessageType.ERROR, error_handler)

        # Send text
        await self.send(
            create_text_message(
                data=text,
                session_id=self.session_id,
            )
        )

        # Stream audio chunks
        while not self._eos_event.is_set():
            try:
                audio = await asyncio.wait_for(
                    self._audio_queue.get(),
                    timeout=1.0,
                )
                yield AudioChunk(
                    data=audio,
                    format=self.config.get("output_format", "pcm_int16"),
                    sample_rate=DEFAULT_SAMPLE_RATE,
                    is_final=False,
                )
            except asyncio.TimeoutError:
                continue

        self._eos_event.clear()

    async def synthesize_full(self, text: str) -> bytes:
        """Synthesize and return complete audio.

        Args:
            text: Text to synthesize

        Returns:
            Raw audio bytes

        Raises:
            ConfigurationError: If text is empty
        """
        audio_chunks = []

        async for chunk in self.synthesize(text):
            audio_chunks.append(chunk.data)

        return b"".join(audio_chunks)

    async def synthesize_to_file(
        self,
        text: str,
        output_path: str | Path,
    ) -> None:
        """Synthesize and save to file.

        Args:
            text: Text to synthesize
            output_path: Output WAV file path

        Raises:
            ConfigurationError: If text is empty
        """
        audio_chunks = []

        async for chunk in self.synthesize(text):
            audio_chunks.append(chunk.data)

        # Combine and save as WAV
        combined = b"".join(audio_chunks)
        AudioHandler.save_wav(combined, output_path)
