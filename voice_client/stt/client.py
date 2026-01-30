"""Speech-to-Text (STT) client for the voice server."""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from voice_client.audio import AudioHandler
from voice_client.client import BaseClient
from voice_client.constants import DEFAULT_CHUNK_MS, DEFAULT_SAMPLE_RATE, DEFAULT_TIMEOUT
from voice_client.exceptions import TimeoutError as VoiceTimeoutError
from voice_client.protocol import (
    Message,
    MessageType,
    TextMessage,
    create_audio_message,
    create_config_message,
    create_eos_message,
)
from voice_client.stt.result import TranscriptionResult


class STTClient(BaseClient):
    """Speech-to-Text client with automatic audio handling.

    Attributes:
        endpoint: WebSocket endpoint for STT
    """

    endpoint = "stt"

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the STT client.

        Args:
            url: WebSocket server URL
            api_key: Optional API key for authentication
            config: Optional configuration for STT
            **kwargs: Additional arguments passed to BaseClient
        """
        super().__init__(url, api_key, **kwargs)
        self.config = {
            "streaming_mode": "both",
            "input_format": "int16",
            **(config or {}),
        }
        self._transcriptions: list[str] = []
        self._final_event = asyncio.Event()

    async def configure(self) -> None:
        """Send configuration to the server."""
        await self.send(
            create_config_message(
                data=self.config,
                session_id=self.session_id,
            )
        )

    async def send_audio(
        self,
        audio: str | bytes | Path,
        chunk_size_ms: int = DEFAULT_CHUNK_MS,
    ) -> None:
        """Send audio for transcription.

        Args:
            audio: File path, file-like object, or raw bytes
            chunk_size_ms: Target chunk duration in milliseconds

        Raises:
            AudioFormatError: If audio format is invalid
        """
        # Load audio
        if isinstance(audio, (str, Path)):
            audio_bytes, sample_rate = AudioHandler.load_audio_file(audio)
        else:
            audio_bytes = audio
            sample_rate = DEFAULT_SAMPLE_RATE  # Assume default

        # Validate
        AudioHandler.validate_audio(audio_bytes, sample_rate)

        # Calculate chunk size
        chunk_size = AudioHandler.calculate_chunk_size(sample_rate, chunk_size_ms)

        # Send chunks
        for chunk in AudioHandler.chunk_audio(audio_bytes, chunk_size):
            await self.send(
                create_audio_message(
                    data=chunk,
                    session_id=self.session_id,
                    sample_rate=sample_rate,
                )
            )

    async def send_eos(self) -> None:
        """Signal end of audio stream."""
        await self.send(create_eos_message(session_id=self.session_id))

    async def get_transcription(self, timeout: float = DEFAULT_TIMEOUT) -> str:
        """Wait for final transcription.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            Transcribed text

        Raises:
            VoiceTimeoutError: If transcription doesn't complete in time
        """
        try:
            await asyncio.wait_for(self._final_event.wait(), timeout=timeout)
            return " ".join(self._transcriptions)
        except asyncio.TimeoutError as e:
            raise VoiceTimeoutError(f"Transcription timed out after {timeout}s") from e
        finally:
            self._final_event.clear()
            self._transcriptions = []

    async def stream_transcription(self) -> AsyncIterator[TranscriptionResult]:
        """Stream transcription results as they arrive.

        Yields:
            TranscriptionResult with partial and final results
        """
        queue: asyncio.Queue[TranscriptionResult] = asyncio.Queue()

        async def handler(msg: Message) -> None:
            if isinstance(msg, TextMessage):
                result = TranscriptionResult(
                    text=str(msg.data),
                    is_final=msg.is_final,
                    confidence=msg.confidence or 0.0,
                )
                await queue.put(result)

                if msg.is_final:
                    self._transcriptions.append(str(msg.data))
                    self._final_event.set()

        self.on_message(MessageType.TEXT, handler)
        self._final_event.clear()

        while True:
            result = await queue.get()
            yield result

            if result.is_final:
                break

    async def transcribe(
        self,
        audio: str | bytes | Path,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> str:
        """Convenience method: send audio and get transcription.

        Args:
            audio: File path or audio bytes
            timeout: Maximum time to wait for result

        Returns:
            Transcribed text
        """
        # Register handler
        async def handler(msg: Message) -> None:
            if isinstance(msg, TextMessage) and msg.is_final:
                self._transcriptions.append(str(msg.data))
                self._final_event.set()

        self.on_message(MessageType.TEXT, handler)
        self._final_event.clear()

        # Send audio
        await self.send_audio(audio)
        await self.send_eos()

        # Wait for result
        return await self.get_transcription(timeout)
