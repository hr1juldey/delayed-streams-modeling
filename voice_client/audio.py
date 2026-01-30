"""
Audio file handler for the voice client SDK.

Handles audio file loading, validation, chunking, and WAV file operations.
"""

import wave
from pathlib import Path

from voice_client.exceptions import AudioFormatError


class AudioHandler:
    """Handle audio file loading, validation, and chunking.

    Class attributes:
        DEFAULT_SAMPLE_RATE: Default sample rate in Hz
        DEFAULT_CHANNELS: Default number of channels (mono)
        DEFAULT_BYTES_PER_SAMPLE: Bytes per sample (16-bit = 2)
        OPTIMAL_CHUNK_SIZE: Default chunk size in bytes (~85ms at 24kHz)
    """

    DEFAULT_SAMPLE_RATE = 24000
    DEFAULT_CHANNELS = 1
    DEFAULT_BYTES_PER_SAMPLE = 2  # int16
    OPTIMAL_CHUNK_SIZE = 4096  # bytes, ~85ms at 24kHz int16

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
                header = f.read(12)
        except OSError as e:
            raise AudioFormatError(f"Could not read file: {e}") from e

        # Check file magic bytes
        if len(header) >= 4 and header[:4] == b"RIFF":
            if len(header) >= 12 and header[8:12] == b"WAVE":
                return cls._load_wav(path)

        if len(header) >= 3:
            if header[:3] == b"ID3" or header[:2] in (
                b"\xff\xfb",
                b"\xff\xfa",
                b"\xff\xfa",
                b"\xff\xff",
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
                if channels != 1:
                    raise AudioFormatError(
                        f"Expected mono audio (1 channel), got {channels} channels. "
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
        return data, cls.DEFAULT_SAMPLE_RATE

    @classmethod
    def validate_audio(
        cls,
        audio_bytes: bytes,
        sample_rate: int,
        channels: int = 1,
        bytes_per_sample: int = 2,
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

        if sample_rate not in (16000, 24000):
            raise AudioFormatError(
                f"Unsupported sample rate: {sample_rate} Hz. Expected 16000 or 24000 Hz."
            )

        if channels != 1:
            raise AudioFormatError(
                f"Unsupported channel count: {channels}. Expected mono (1 channel)."
            )

        if bytes_per_sample != 2:
            raise AudioFormatError(
                f"Unsupported bit depth: {bytes_per_sample * 8}-bit. "
                "Expected 16-bit (2 bytes per sample)."
            )

        # Validate data length
        samples = len(audio_bytes) // (channels * bytes_per_sample)
        if samples == 0:
            raise AudioFormatError("Audio data is too short (no samples)")

    @classmethod
    def calculate_chunk_size(cls, sample_rate: int, target_ms: int = 80) -> int:
        """Calculate optimal chunk size for a target duration.

        Args:
            sample_rate: Audio sample rate in Hz
            target_ms: Target chunk duration in milliseconds

        Returns:
            Number of bytes per chunk
        """
        bytes_per_sample = cls.DEFAULT_BYTES_PER_SAMPLE
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
            chunk_size = cls.OPTIMAL_CHUNK_SIZE

        chunks = []
        for i in range(0, len(audio), chunk_size):
            chunks.append(audio[i : i + chunk_size])
        return chunks

    @classmethod
    def save_wav(
        cls,
        audio: bytes,
        path: str | Path,
        sample_rate: int = 24000,
        channels: int = 1,
        sampwidth: int = 2,
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
