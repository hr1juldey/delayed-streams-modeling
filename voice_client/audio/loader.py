"""Audio file loader supporting WAV and raw PCM formats."""

import wave
from pathlib import Path

from voice_client.constants import (
    DEFAULT_CHANNELS,
    DEFAULT_SAMPLE_RATE,
    MP3_FRAME_MAGICS,
    MP3_ID3_MAGIC,
    WAV_RIFF_HEADER_SIZE,
    WAV_RIFF_MAGIC,
    WAV_WAVE_MAGIC,
)
from voice_client.exceptions import AudioFormatError


class AudioLoader:
    """Load audio files with auto-detection of format."""

    @classmethod
    def load_audio_file(cls, path: str | Path) -> tuple[bytes, int]:
        """Load audio file, auto-detect format.

        Args:
            path: Path to the audio file

        Returns:
            tuple of (audio_bytes, sample_rate)

        Raises:
            AudioFormatError: If file format is invalid or unsupported
        """
        path = Path(path)
        if not path.exists():
            raise AudioFormatError(
                f"File not found: {path}. Please check the file path and try again."
            )

        # Read first 12 bytes for magic number detection
        try:
            with open(path, "rb") as f:
                header = f.read(WAV_RIFF_HEADER_SIZE)
        except OSError as e:
            raise AudioFormatError(f"Could not read file: {e}") from e

        # Check file magic bytes
        if (
            len(header) >= 4
            and header[:4] == WAV_RIFF_MAGIC
            and len(header) >= 12
            and header[8:12] == WAV_WAVE_MAGIC
        ):
            return cls._load_wav(path)

        if len(header) >= 3 and (
            header[:3] == MP3_ID3_MAGIC or header[:2] in MP3_FRAME_MAGICS
        ):
            raise AudioFormatError(
                "MP3 files are not supported directly. "
                "Convert to WAV first: "
                "ffmpeg -i input.mp3 -ar 24000 -ac 1 output.wav"
            )

        # Assume raw PCM
        return cls._load_raw(path)

    @classmethod
    def _load_wav(cls, path: Path) -> tuple[bytes, int]:
        """Load WAV file and extract PCM data.

        Args:
            path: Path to the WAV file

        Returns:
            tuple of (audio_bytes, sample_rate)

        Raises:
            AudioFormatError: If WAV format is invalid
        """
        try:
            with wave.open(str(path), "rb") as wav:
                channels = wav.getnchannels()
                sampwidth = wav.getsampwidth()
                sample_rate = wav.getframerate()

                # Validate format
                if channels != DEFAULT_CHANNELS:
                    raise AudioFormatError(
                        f"Expected mono audio ({DEFAULT_CHANNELS} channel), "
                        f"got {channels} channels. "
                        "Convert with: ffmpeg -i input.wav -ac 1 output.wav"
                    )

                if sampwidth != 2:
                    raise AudioFormatError(
                        f"Expected 16-bit audio (2 bytes per sample), got {sampwidth * 8}-bit. "
                        "Convert with: ffmpeg -i input.wav -acodec pcm_s16le output.wav"
                    )

                frames = wav.readframes(wav.getnframes())
                return frames, sample_rate

        except wave.Error as e:
            raise AudioFormatError(f"Invalid WAV file: {e}") from e

    @classmethod
    def _load_raw(cls, path: Path) -> tuple[bytes, int]:
        """Load raw PCM file (assumes 24kHz, 16-bit, mono).

        Args:
            path: Path to the raw PCM file

        Returns:
            tuple of (audio_bytes, sample_rate)
        """
        with open(path, "rb") as f:
            data = f.read()
        return data, DEFAULT_SAMPLE_RATE
