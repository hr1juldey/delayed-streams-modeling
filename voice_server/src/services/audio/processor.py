"""Audio processor for format conversion and audio stream processing.

Handles audio format conversions, normalization, and stream processing.
"""

import asyncio
import numpy as np
from typing import AsyncIterator, Optional, Union

from voice_server.config.logging_config import get_logger
from voice_server.config.settings import AudioSettings
from voice_server.src.utils.audio import (
    resample,
    normalize_audio,
    float32_to_int16,
    int16_to_float32,
    bytes_to_int16,
    bytes_to_float32,
    int16_to_bytes,
    float32_to_bytes,
    add_wav_header,
)

logger = get_logger(__name__)


class AudioProcessor:
    """Processes audio streams with format conversion and normalization.

    Features:
    - Format conversion (int16, float32, WAV)
    - Sample rate conversion
    - Audio normalization
    - Chunk-based processing
    """

    def __init__(self, settings: AudioSettings):
        """Initialize the audio processor.

        Args:
            settings: Audio configuration settings.
        """
        self.settings = settings
        self._converter = None

    async def process_input_chunk(
        self,
        audio_data: bytes,
        input_format: Optional[str] = None,
    ) -> np.ndarray:
        """Process an incoming audio chunk to internal format.

        Converts input audio to float32 and resamples if needed.

        Args:
            audio_data: Raw audio bytes.
            input_format: Input format (int16, float32, wav). Defaults to settings.

        Returns:
            Processed audio as float32 numpy array.
        """
        input_format = input_format or self.settings.input_format

        try:
            # Parse input format
            if input_format == "int16":
                audio = int16_to_float32(bytes_to_int16(audio_data))
            elif input_format == "float32":
                audio = bytes_to_float32(audio_data)
            elif input_format == "wav":
                from src.utils.audio import parse_wav
                audio_bytes, sr, _, _ = parse_wav(audio_data)
                audio = int16_to_float32(audio_bytes)
                # Resample if needed
                if sr != self.settings.input_sample_rate:
                    audio = resample(audio, sr, self.settings.input_sample_rate)
            else:
                raise ValueError(f"Unknown input format: {input_format}")

            return audio

        except Exception as e:
            logger.error(f"Error processing input audio: {e}")
            raise

    async def process_output_chunk(
        self,
        audio: np.ndarray,
        output_format: Optional[str] = None,
        normalize: bool = False,
    ) -> bytes:
        """Process audio for output to client.

        Converts internal float32 format to requested output format.

        Args:
            audio: Audio array as float32.
            output_format: Output format (int16, float32, wav).
            normalize: Whether to normalize audio.

        Returns:
            Processed audio as bytes.
        """
        output_format = output_format or self.settings.output_format

        try:
            # Normalize if requested
            if normalize:
                audio = normalize_audio(audio)

            # Convert to output format
            if output_format == "pcm_int16":
                result = int16_to_bytes(float32_to_int16(audio))
            elif output_format == "pcm_float32":
                result = float32_to_bytes(audio)
            elif output_format == "wav":
                pcm_bytes = int16_to_bytes(float32_to_int16(audio))
                result = add_wav_header(pcm_bytes, self.settings.output_sample_rate)
            else:
                raise ValueError(f"Unknown output format: {output_format}")

            return result

        except Exception as e:
            logger.error(f"Error processing output audio: {e}")
            raise

    async def process_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        input_format: Optional[str] = None,
        output_format: Optional[str] = None,
    ) -> AsyncIterator[np.ndarray]:
        """Process a stream of audio chunks.

        Args:
            audio_stream: Async iterator of audio bytes.
            input_format: Input format for each chunk.
            output_format: Desired output format.

        Yields:
            Processed audio arrays as float32.
        """
        async for chunk in audio_stream:
            processed = await self.process_input_chunk(chunk, input_format)
            yield processed

    def calculate_chunk_size_bytes(
        self,
        chunk_duration_ms: int,
        format: str = "int16",
        sample_rate: Optional[int] = None,
    ) -> int:
        """Calculate the byte size for a chunk duration.

        Args:
            chunk_duration_ms: Chunk duration in milliseconds.
            format: Audio format (int16, float32).
            sample_rate: Sample rate (defaults to input_sample_rate).

        Returns:
            Number of bytes for the chunk.
        """
        sample_rate = sample_rate or self.settings.input_sample_rate
        samples_per_channel = (sample_rate * chunk_duration_ms) // 1000

        if format == "int16":
            bytes_per_sample = 2
        elif format == "float32":
            bytes_per_sample = 4
        else:
            raise ValueError(f"Unknown format: {format}")

        return samples_per_channel * bytes_per_sample

    def validate_audio_chunk(
        self,
        audio_data: bytes,
        expected_format: Optional[str] = None,
    ) -> bool:
        """Validate an audio chunk.

        Args:
            audio_data: Audio bytes to validate.
            expected_format: Expected format (int16, float32, wav).

        Returns:
            True if valid, False otherwise.
        """
        expected_format = expected_format or self.settings.input_format

        try:
            if not audio_data:
                return False

            if expected_format == "int16":
                # Should be divisible by 2 (int16 = 2 bytes)
                if len(audio_data) % 2 != 0:
                    return False
            elif expected_format == "float32":
                # Should be divisible by 4 (float32 = 4 bytes)
                if len(audio_data) % 4 != 0:
                    return False
            elif expected_format == "wav":
                # Should have WAV header
                if len(audio_data) < 44:
                    return False
                if not audio_data[:4] == b"RIFF":
                    return False

            return True

        except Exception:
            return False

    async def convert_sample_rate(
        self,
        audio: np.ndarray,
        from_sr: int,
        to_sr: int,
    ) -> np.ndarray:
        """Convert audio sample rate.

        Args:
            audio: Input audio array.
            from_sr: Source sample rate.
            to_sr: Target sample rate.

        Returns:
            Resampled audio array.
        """
        if from_sr == to_sr:
            return audio

        # Run in thread pool to avoid blocking
        return await asyncio.to_thread(resample, audio, from_sr, to_sr)

    async def normalize_chunk(
        self,
        audio: np.ndarray,
        target_db: float = -3.0,
    ) -> np.ndarray:
        """Normalize audio chunk to target dB level.

        Args:
            audio: Input audio array.
            target_db: Target level in dB.

        Returns:
            Normalized audio array.
        """
        # Run in thread pool to avoid blocking
        return await asyncio.to_thread(normalize_audio, audio, target_db)


class StreamProcessor:
    """Processes continuous audio streams with buffering.

    Features:
    - Stream buffering and alignment
    - Chunk-based processing
    - Backpressure handling
    """

    def __init__(
        self,
        processor: AudioProcessor,
        chunk_size_samples: int,
    ):
        """Initialize the stream processor.

        Args:
            processor: Audio processor instance.
            chunk_size_samples: Target chunk size in samples.
        """
        self.processor = processor
        self.chunk_size_samples = chunk_size_samples
        self._buffer: list[np.ndarray] = []
        self._buffer_size_samples = 0

    async def process_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        input_format: str = "int16",
    ) -> AsyncIterator[np.ndarray]:
        """Process audio stream into fixed-size chunks.

        Args:
            audio_stream: Async iterator of audio bytes.
            input_format: Input audio format.

        Yields:
            Fixed-size audio chunks as float32 arrays.
        """
        async for audio_bytes in audio_stream:
            # Process input chunk
            audio = await self.processor.process_input_chunk(audio_bytes, input_format)

            # Add to buffer
            self._buffer.append(audio)
            self._buffer_size_samples += len(audio)

            # Yield complete chunks
            while self._buffer_size_samples >= self.chunk_size_samples:
                yield await self._get_next_chunk()

        # Yield remaining partial buffer
        if self._buffer_size_samples > 0:
            yield await self._get_final_chunk()

    async def _get_next_chunk(self) -> np.ndarray:
        """Get the next chunk from the buffer.

        Returns:
            Audio chunk of exactly chunk_size_samples.
        """
        # Collect samples for chunk
        result_samples = []
        samples_needed = self.chunk_size_samples

        while samples_needed > 0 and self._buffer:
            current = self._buffer[0]

            if len(current) <= samples_needed:
                # Take entire buffer entry
                result_samples.append(current)
                samples_needed -= len(current)
                self._buffer.pop(0)
            else:
                # Take part of buffer entry
                result_samples.append(current[:samples_needed])
                self._buffer[0] = current[samples_needed:]
                samples_needed = 0

        self._buffer_size_samples -= self.chunk_size_samples

        # Concatenate samples
        if len(result_samples) == 1:
            return result_samples[0]
        else:
            return np.concatenate(result_samples)

    async def _get_final_chunk(self) -> np.ndarray:
        """Get the final partial chunk from the buffer.

        Returns:
            Audio chunk (may be smaller than chunk_size_samples).
        """
        if not self._buffer:
            return np.array([], dtype=np.float32)

        if len(self._buffer) == 1:
            result = self._buffer[0]
            self._buffer.clear()
        else:
            result = np.concatenate(self._buffer)
            self._buffer.clear()

        self._buffer_size_samples = 0
        return result

    def reset(self) -> None:
        """Reset the stream processor buffer."""
        self._buffer.clear()
        self._buffer_size_samples = 0

    @property
    def buffer_size_samples(self) -> int:
        """Get current buffer size in samples."""
        return self._buffer_size_samples

    @property
    def buffer_size_ms(self) -> float:
        """Get current buffer size in milliseconds."""
        return (self._buffer_size_samples / self.processor.settings.input_sample_rate) * 1000
