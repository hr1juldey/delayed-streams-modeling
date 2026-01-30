"""Audio format validation."""

from voice_client.constants import (
    SUPPORTED_BYTES_PER_SAMPLE,
    SUPPORTED_CHANNELS,
    SUPPORTED_SAMPLE_RATES,
)
from voice_client.exceptions import AudioFormatError


class AudioValidator:
    """Validate audio format parameters."""

    @classmethod
    def validate_audio(
        cls,
        audio_bytes: bytes,
        sample_rate: int,
        channels: int = SUPPORTED_CHANNELS,
        bytes_per_sample: int = SUPPORTED_BYTES_PER_SAMPLE,
    ) -> None:
        """Validate audio format parameters.

        Args:
            audio_bytes: Raw audio data
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
            bytes_per_sample: Bytes per sample

        Raises:
            AudioFormatError: If any parameter is invalid
        """
        if not audio_bytes:
            raise AudioFormatError("Audio data is empty")

        if sample_rate not in SUPPORTED_SAMPLE_RATES:
            raise AudioFormatError(
                f"Unsupported sample rate: {sample_rate} Hz. "
                f"Expected {SUPPORTED_SAMPLE_RATES} Hz."
            )

        if channels != SUPPORTED_CHANNELS:
            raise AudioFormatError(
                f"Unsupported channel count: {channels}. "
                f"Expected mono ({SUPPORTED_CHANNELS} channel)."
            )

        if bytes_per_sample != SUPPORTED_BYTES_PER_SAMPLE:
            raise AudioFormatError(
                f"Unsupported bit depth: {bytes_per_sample * 8}-bit. "
                "Expected 16-bit (2 bytes per sample)."
            )

        # Validate data length
        samples = len(audio_bytes) // (channels * bytes_per_sample)
        if samples == 0:
            raise AudioFormatError("Audio data is too short (no samples)")
