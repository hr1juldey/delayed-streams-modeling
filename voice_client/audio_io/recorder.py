"""Audio recorder for microphone input."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import numpy as np
import sounddevice as sd

from voice_client.audio_io.devices import list_input_devices
from voice_client.constants import (
    DEFAULT_CHANNELS,
    DEFAULT_CHUNK_MS,
    DEFAULT_SAMPLE_RATE,
    SILENCE_DURATION_MS,
    SILENCE_THRESHOLD,
)


class AudioRecorder:
    """Record audio from microphone using sounddevice.

    Attributes:
        DEFAULT_SAMPLE_RATE: Default sample rate in Hz
        DEFAULT_CHANNELS: Default number of channels (mono)
        DEFAULT_DTYPE: Default numpy dtype for audio
    """

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
        return list_input_devices()

    def record(
        self,
        duration_seconds: float,
        silence_threshold: float = SILENCE_THRESHOLD,
    ) -> tuple[np.ndarray, int]:
        """Record audio for a fixed duration.

        Args:
            duration_seconds: How long to record in seconds
            silence_threshold: RMS threshold for silence detection

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
        chunk_size_ms: int = DEFAULT_CHUNK_MS,
        silence_threshold: float = SILENCE_THRESHOLD,
        silence_duration_ms: float = SILENCE_DURATION_MS,
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
        threshold: float = SILENCE_THRESHOLD,
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
