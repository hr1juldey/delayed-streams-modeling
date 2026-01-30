"""Audio processing utilities for chunking."""

from voice_client.constants import DEFAULT_BYTES_PER_SAMPLE, OPTIMAL_CHUNK_SIZE


class AudioProcessor:
    """Process audio data for streaming."""

    @classmethod
    def calculate_chunk_size(cls, sample_rate: int, target_ms: int = 80) -> int:
        """Calculate optimal chunk size for a target duration.

        Args:
            sample_rate: Audio sample rate in Hz
            target_ms: Target chunk duration in milliseconds

        Returns:
            Number of bytes per chunk
        """
        bytes_per_sample = DEFAULT_BYTES_PER_SAMPLE
        samples_per_chunk = (sample_rate * target_ms) // 1000
        return samples_per_chunk * bytes_per_sample

    @classmethod
    def chunk_audio(cls, audio: bytes, chunk_size: int | None = None) -> list[bytes]:
        """Split audio into optimal chunks.

        Args:
            audio: Raw audio bytes
            chunk_size: Bytes per chunk (auto-calculated if None)

        Returns:
            List of audio chunks
        """
        if chunk_size is None:
            chunk_size = OPTIMAL_CHUNK_SIZE

        chunks = []
        for i in range(0, len(audio), chunk_size):
            chunks.append(audio[i : i + chunk_size])
        return chunks
