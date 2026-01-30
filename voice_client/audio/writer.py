"""Audio file writer for WAV format."""

import wave
from pathlib import Path

from voice_client.constants import DEFAULT_CHANNELS, DEFAULT_SAMPLE_RATE, WAV_BYTES_PER_SAMPLE


class AudioWriter:
    """Write audio files to disk."""

    @classmethod
    def save_wav(
        cls,
        audio: bytes,
        path: str | Path,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        sampwidth: int = WAV_BYTES_PER_SAMPLE,
    ) -> None:
        """Save audio as a WAV file.

        Args:
            audio: Raw audio bytes
            path: Output file path
            sample_rate: Sample rate in Hz
            channels: Number of channels
            sampwidth: Bytes per sample (2 for 16-bit)
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        samples = len(audio) // (channels * sampwidth)

        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(sampwidth)
            wav.setframerate(sample_rate)
            wav.setnframes(samples)
            wav.writeframes(audio)
