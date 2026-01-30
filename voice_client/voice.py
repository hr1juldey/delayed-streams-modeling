"""
Combined STT + TTS client for full conversations.

Provides a unified interface for speech-to-text transcription,
agent processing, and text-to-speech synthesis.
"""

import asyncio
import types
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from typing_extensions import Self

from voice_client.stt import STTClient, TranscriptionResult
from voice_client.tts import AudioChunk, TTSClient


@dataclass
class ConversationEvent:
    """Event from a streaming conversation.

    Attributes:
        type: Event type ("stt_partial", "stt_final", "tts_audio", "complete")
        data: Event data (varies by type)
        timestamp: Event timestamp
    """

    type: str
    data: TranscriptionResult | AudioChunk | None
    timestamp: float


class VoiceClient:
    """Combined STT + TTS client for full conversations.

    Attributes:
        stt: The STT client instance
        tts: The TTS client instance
    """

    def __init__(
        self,
        stt_url: str | None = None,
        tts_url: str | None = None,
        url: str | None = None,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the voice client.

        Args:
            stt_url: Optional STT WebSocket URL
            tts_url: Optional TTS WebSocket URL
            url: Shared base URL (appends /stt and /tts)
            api_key: Optional API key for authentication
            **kwargs: Additional arguments passed to clients
        """
        # Handle URL construction
        if url and not (stt_url or tts_url):
            stt_url = url
            tts_url = url

        self.stt = STTClient(stt_url, api_key, **kwargs)
        self.tts = TTSClient(tts_url, api_key, **kwargs)

    async def __aenter__(self) -> Self:
        """Enter the async context manager.

        Returns:
            The connected voice client instance
        """
        try:
            await self.stt.__aenter__()
            await self.tts.__aenter__()
            return self
        except Exception:
            # If TTS connection fails, close STT connection
            await self.stt.__aexit__(None, None, None)
            raise

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Exit the async context manager.

        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        await self.stt.__aexit__(exc_type, exc_val, exc_tb)
        await self.tts.__aexit__(exc_type, exc_val, exc_tb)

    async def converse(
        self,
        audio: str | bytes,
        agent_callback: Any = None,
    ) -> tuple[str, bytes]:
        """Full conversation: STT → Agent → TTS.

        Args:
            audio: User speech input (file path or bytes)
            agent_callback: Optional function to process transcription and return response

        Returns:
            Tuple of (transcription, response_audio)

        Raises:
            Exception: Propagates any errors from STT or TTS
        """
        # Step 1: Transcribe
        transcription = await self.stt.transcribe(audio)

        # Step 2: Process with agent
        if agent_callback:
            if asyncio.iscoroutinefunction(agent_callback):
                response_text = await agent_callback(transcription)
            else:
                response_text = agent_callback(transcription)
        else:
            response_text = f"You said: {transcription}"

        # Step 3: Synthesize response
        response_audio = await self.tts.synthesize_full(response_text)

        return transcription, response_audio

    async def converse_stream(
        self,
        audio: str | bytes,
        agent_callback: Any = None,
    ) -> AsyncIterator[ConversationEvent]:
        """Stream conversation events in real-time.

        Args:
            audio: User speech input (file path or bytes)
            agent_callback: Optional function to process transcription

        Yields:
            ConversationEvent with updates
        """
        import time

        final_result: TranscriptionResult | None = None

        # Step 1: Stream STT
        async for result in self.stt.stream_transcription():
            if result.is_final:
                final_result = result
                event = ConversationEvent(
                    type="stt_final",
                    data=result,
                    timestamp=time.time(),
                )
                yield event
                break
            else:
                event = ConversationEvent(
                    type="stt_partial",
                    data=result,
                    timestamp=time.time(),
                )
                yield event

        # Make sure we have the final result
        if final_result is None:
            raise RuntimeError("STT stream ended without a final result")

        # Step 2: Process with agent
        transcription = final_result.text
        if agent_callback:
            if asyncio.iscoroutinefunction(agent_callback):
                response_text = await agent_callback(transcription)
            else:
                response_text = agent_callback(transcription)
        else:
            response_text = f"You said: {transcription}"

        # Step 3: Stream TTS
        async for chunk in self.tts.synthesize(response_text):
            event = ConversationEvent(
                type="tts_audio",
                data=chunk,
                timestamp=time.time(),
            )
            yield event

        # Complete
        event = ConversationEvent(
            type="complete",
            data=None,
            timestamp=time.time(),
        )
        yield event
