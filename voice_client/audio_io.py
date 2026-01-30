"""
Audio I/O module for the voice client SDK.

Provides AudioRecorder for microphone input and AudioPlayer for speaker output.
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

import numpy as np
import sounddevice as sd

from voice_client.exceptions import PlaybackError


class AudioRecorder:
    """Record audio from microphone using sounddevice.

    Attributes:
        DEFAULT_SAMPLE_RATE: Default sample rate in Hz
        DEFAULT_CHANNELS: Default number of channels (mono)
        DEFAULT_DTYPE: Default numpy dtype for audio
    """

    DEFAULT_SAMPLE_RATE = 24000
    DEFAULT_CHANNELS = 1
    DEFAULT_DTYPE = np.int16

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        device: int | None = None,
    ) -> None:
        """Initialize the audio recorder.

        Args:
            sample_rate: Sample rate in Hz (default: 24000)
            channels: Number of audio channels (default: 1 for mono)
            device: Device index (None for system default)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self._stream: sd.InputStream | None = None

    @classmethod
    def list_devices(cls) -> list[dict[str, Any]]:
        """List available audio input devices.

        Returns:
            List of device dictionaries with keys:
            - index: device index
            - name: device name
            - channels: maximum input channels
            - sample_rate: default sample rate
        """
        devices = []
        device_list = sd.query_devices()
        for i, info in enumerate(device_list):
            # Handle both dict-like and object-like device info
            if isinstance(info, dict):
                max_input = info.get("max_input_channels", 0)
                name = info.get("name", f"Device {i}")
                samplerate = info.get("default_samplerate", 48000)
            else:
                max_input = info.max_input_channels
                name = info.name
                samplerate = info.default_samplerate

            if max_input > 0:
                devices.append(
                    {
                        "index": i,
                        "name": name,
                        "channels": max_input,
                        "sample_rate": samplerate,
                    }
                )
        return devices

    def record(
        self,
        duration_seconds: float,
        silence_threshold: float = 0.01,
    ) -> tuple[np.ndarray, int]:
        """Record audio for a fixed duration.

        Args:
            duration_seconds: How long to record in seconds
            silence_threshold: RMS threshold for silence detection (default: 0.01)

        Returns:
            Tuple of (audio_array, sample_rate)
        """
        frames = int(duration_seconds * self.sample_rate)
        recording = sd.rec(
            frames,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=self.DEFAULT_DTYPE,
            device=self.device,
        )
        sd.wait()

        # Trim leading/trailing silence
        return self._trim_silence(recording, silence_threshold), self.sample_rate

    async def record_stream(
        self,
        chunk_size_ms: int = 80,
        silence_threshold: float = 0.01,
        silence_duration_ms: float = 1000,
    ) -> AsyncIterator[bytes]:
        """Record audio in chunks, stop on silence.

        Args:
            chunk_size_ms: Audio chunk duration in milliseconds
            silence_threshold: RMS threshold for silence detection
            silence_duration_ms: Milliseconds of silence to trigger stop

        Yields:
            Audio chunks as bytes
        """
        chunk_size = (self.sample_rate * chunk_size_ms) // 1000
        silence_chunks = (self.sample_rate * silence_duration_ms) // 1000

        queue: asyncio.Queue[tuple[bytes, bool]] = asyncio.Queue()

        def audio_callback(indata: np.ndarray, frames: int, time: Any, status: Any) -> None:
            """Callback for each audio chunk.

            Args:
                indata: Input audio data
                frames: Number of frames
                time: Stream time
                status: Stream status
            """
            if status:
                print(f"Audio callback status: {status}")
                return

            # Detect silence using RMS
            rms = float(np.sqrt(np.mean(indata**2)))
            is_silent = rms < silence_threshold

            audio_bytes = indata.tobytes()

            # Put in queue with silence flag
            try:
                loop = asyncio.get_event_loop()
                asyncio.run_coroutine_threadsafe(
                    queue.put((audio_bytes, is_silent)),
                    loop,
                )
            except RuntimeError:
                # Event loop closed
                pass

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=self.DEFAULT_DTYPE,
            blocksize=chunk_size,
            callback=audio_callback,
            device=self.device,
        )

        self._stream.start()

        silence_count = 0
        try:
            while True:
                try:
                    chunk, is_silent = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Check if stream is still active
                    if self._stream and not self._stream.active:
                        break
                    continue

                if is_silent:
                    silence_count += chunk_size
                    if silence_count >= silence_chunks:
                        # Enough silence, stop recording
                        break
                else:
                    silence_count = 0

                yield chunk

        finally:
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None

    def _trim_silence(
        self,
        audio: np.ndarray,
        threshold: float = 0.01,
    ) -> np.ndarray:
        """Remove leading and trailing silence from audio.

        Args:
            audio: Audio array
            threshold: Silence threshold (RMS)

        Returns:
            Audio array with silence trimmed
        """
        # Find first non-silent sample
        start = 0
        for i in range(len(audio)):
            if abs(audio[i]) > threshold:
                start = i
                break
        else:
            # All silence
            return np.array([], dtype=audio.dtype)

        # Find last non-silent sample
        end = len(audio) - 1
        for i in range(len(audio) - 1, -1, -1):
            if abs(audio[i]) > threshold:
                end = i
                break

        return audio[start : end + 1]


class AudioPlayer:
    """Play audio using sounddevice.

    Attributes:
        DEFAULT_SAMPLE_RATE: Default sample rate in Hz
        DEFAULT_CHANNELS: Default number of channels (mono)
    """

    DEFAULT_SAMPLE_RATE = 24000
    DEFAULT_CHANNELS = 1

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
        devices = []
        device_list = sd.query_devices()
        for i, info in enumerate(device_list):
            # Handle both dict-like and object-like device info
            if isinstance(info, dict):
                max_output = info.get("max_output_channels", 0)
                name = info.get("name", f"Device {i}")
                samplerate = info.get("default_samplerate", 48000)
            else:
                max_output = info.max_output_channels
                name = info.name
                samplerate = info.default_samplerate

            if max_output > 0:
                devices.append(
                    {
                        "index": i,
                        "name": name,
                        "channels": max_output,
                        "sample_rate": samplerate,
                    }
                )
        return devices

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
