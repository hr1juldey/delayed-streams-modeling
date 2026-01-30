"""Audio player for speaker output."""

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

import numpy as np
import sounddevice as sd

from voice_client.audio_io.devices import list_output_devices
from voice_client.constants import DEFAULT_CHANNELS, DEFAULT_SAMPLE_RATE
from voice_client.exceptions import PlaybackError


class AudioPlayer:
    """Play audio using sounddevice.

    Attributes:
        DEFAULT_SAMPLE_RATE: Default sample rate in Hz
        DEFAULT_CHANNELS: Default number of channels (mono)
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        device: int | None = None,
    ) -> None:
        """Initialize the audio player.

        Args:
            sample_rate: Sample rate in Hz (default: 24000)
            channels: Number of audio channels (default: 1 for mono)
            device: Device index (None for system default)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device

    @classmethod
    def list_devices(cls) -> list[dict[str, Any]]:
        """List available audio output devices.

        Returns:
            List of device dictionaries with keys:
            - index: device index
            - name: device name
            - channels: maximum output channels
            - sample_rate: default sample rate
        """
        return list_output_devices()

    def play(self, audio: bytes | np.ndarray) -> None:
        """Play audio and wait for completion.

        Args:
            audio: Audio bytes or numpy array

        Raises:
            PlaybackError: If playback fails
        """
        try:
            if isinstance(audio, bytes):
                audio = np.frombuffer(audio, dtype=np.int16)

            sd.play(audio, samplerate=self.sample_rate, device=self.device)
            sd.wait()  # Wait until playback is complete
        except Exception as e:
            raise PlaybackError(f"Playback failed: {e}") from e

    async def play_async(
        self,
        audio: bytes | np.ndarray,
        callback: Callable[[], None] | None = None,
    ) -> None:
        """Play audio asynchronously.

        Args:
            audio: Audio bytes or numpy array
            callback: Optional callback when playback completes

        Raises:
            PlaybackError: If playback fails
        """
        try:
            if isinstance(audio, bytes):
                audio = np.frombuffer(audio, dtype=np.int16)

            sd.play(audio, samplerate=self.sample_rate, device=self.device)

            # Wait for completion in a non-blocking way
            while True:
                # Check if still playing
                if sd.get_stream() and sd.get_stream().active:
                    await asyncio.sleep(0.01)
                else:
                    break

            if callback:
                callback()
        except Exception as e:
            raise PlaybackError(f"Async playback failed: {e}") from e

    async def play_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        pre_buffer_chunks: int = 3,
    ) -> None:
        """Stream audio chunks as they arrive (low-latency playback).

        Args:
            audio_stream: Async iterator yielding audio chunks
            pre_buffer_chunks: Number of chunks to buffer before starting playback

        Raises:
            PlaybackError: If playback fails
        """
        try:
            queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=pre_buffer_chunks)

            # Producer task: receive chunks
            async def producer() -> None:
                try:
                    async for chunk in audio_stream:
                        await queue.put(chunk)
                    await queue.put(None)  # Signal end
                except Exception as e:
                    raise PlaybackError(f"Stream producer error: {e}") from e

            # Consumer task: play chunks
            async def consumer() -> None:
                while True:
                    chunk = await queue.get()
                    if chunk is None:
                        break
                    # Play chunk synchronously (for low latency)
                    self.play(chunk)

            # Run both concurrently
            await asyncio.gather(producer(), consumer())
        except Exception as e:
            raise PlaybackError(f"Stream playback failed: {e}") from e

    def stop(self) -> None:
        """Stop any currently playing audio."""
        sd.stop()
