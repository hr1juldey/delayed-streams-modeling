"""Audio utilities for resampling, format conversion, and processing.

Provides utilities for audio resampling using julius, format conversions,
and audio normalization.
"""

import io
import wave
import struct
import numpy as np
from typing import Union, Tuple

from voice_server.config.logging_config import get_logger

logger = get_logger(__name__)

# Try to import julius for resampling
try:
    import julius
    JULIUS_AVAILABLE = True
except ImportError:
    JULIUS_AVAILABLE = False
    logger.warning("julius not available, audio resampling will be limited")


AudioArray = Union[np.ndarray, list]
AudioData = Union[bytes, np.ndarray]


def resample(
    audio: np.ndarray,
    original_sr: int,
    target_sr: int,
) -> np.ndarray:
    """Resample audio to a different sample rate.

    Args:
        audio: Input audio array (float32 or int16).
        original_sr: Original sample rate.
        target_sr: Target sample rate.

    Returns:
        Resampled audio array.

    Raises:
        ValueError: If julius is not available and resampling is needed.
    """
    if original_sr == target_sr:
        return audio

    if not JULIUS_AVAILABLE:
        raise ValueError(
            "julius is required for resampling. "
            "Install it with: pip install julius"
        )

    # Convert to float32 if needed
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0

    # Ensure 2D array (channels, samples)
    if audio.ndim == 1:
        audio = audio.reshape(1, -1)

    # Resample using julius
    resampled = julius.resample_frac(audio, original_sr, target_sr)

    return resampled


def normalize_audio(audio: np.ndarray, target_db: float = -3.0) -> np.ndarray:
    """Normalize audio to a target dB level.

    Args:
        audio: Input audio array (float32, values -1.0 to 1.0).
        target_db: Target level in dB (typically -3.0 to 0.0).

    Returns:
        Normalized audio array.
    """
    # Avoid division by zero
    peak = np.max(np.abs(audio))
    if peak < 1e-8:
        return audio

    # Calculate current level in dB
    current_db = 20 * np.log10(peak)

    # Calculate gain needed
    gain = target_db - current_db

    # Apply gain
    gain_linear = 10 ** (gain / 20)
    normalized = audio * gain_linear

    # Clip to prevent distortion
    normalized = np.clip(normalized, -1.0, 1.0)

    return normalized


def float32_to_int16(audio: np.ndarray) -> np.ndarray:
    """Convert float32 audio to int16.

    Args:
        audio: Input audio array (float32, values -1.0 to 1.0).

    Returns:
        Audio array as int16.
    """
    # Clip to valid range
    clipped = np.clip(audio, -1.0, 1.0)

    # Convert to int16
    return (clipped * 32767.0).astype(np.int16)


def int16_to_float32(audio: np.ndarray) -> np.ndarray:
    """Convert int16 audio to float32.

    Args:
        audio: Input audio array (int16).

    Returns:
        Audio array as float32 (values -1.0 to 1.0).
    """
    return audio.astype(np.float32) / 32768.0


def bytes_to_int16(audio_bytes: bytes) -> np.ndarray:
    """Convert raw bytes to int16 numpy array.

    Args:
        audio_bytes: Raw audio bytes.

    Returns:
        Audio array as int16.
    """
    return np.frombuffer(audio_bytes, dtype=np.int16)


def int16_to_bytes(audio: np.ndarray) -> bytes:
    """Convert int16 numpy array to raw bytes.

    Args:
        audio: Audio array as int16.

    Returns:
        Raw audio bytes.
    """
    return audio.tobytes()


def bytes_to_float32(audio_bytes: bytes) -> np.ndarray:
    """Convert raw bytes to float32 numpy array.

    Args:
        audio_bytes: Raw audio bytes (little-endian).

    Returns:
        Audio array as float32.
    """
    return np.frombuffer(audio_bytes, dtype=np.float32)


def float32_to_bytes(audio: np.ndarray) -> bytes:
    """Convert float32 numpy array to raw bytes.

    Args:
        audio: Audio array as float32.

    Returns:
        Raw audio bytes (little-endian).
    """
    return audio.tobytes()


def calculate_rms(audio: np.ndarray) -> float:
    """Calculate the RMS (root mean square) level of audio.

    Args:
        audio: Audio array.

    Returns:
        RMS level.
    """
    return np.sqrt(np.mean(audio ** 2))


def detect_silence(
    audio: np.ndarray,
    threshold: float = 0.01,
    min_duration_samples: int = 2400,
) -> bool:
    """Detect if audio is mostly silent.

    Args:
        audio: Audio array.
        threshold: RMS threshold for silence detection.
        min_duration_samples: Minimum duration to check.

    Returns:
        True if audio is silent, False otherwise.
    """
    samples_to_check = min(len(audio), min_duration_samples)
    if samples_to_check == 0:
        return True

    segment = audio[:samples_to_check]
    rms = calculate_rms(segment)
    return rms < threshold


def create_wav_header(
    sample_rate: int,
    channels: int = 1,
    sample_width: int = 2,
    data_size: int = 0,
) -> bytes:
    """Create a WAV file header.

    Args:
        sample_rate: Sample rate in Hz.
        channels: Number of audio channels.
        sample_width: Bytes per sample (2 for int16).
        data_size: Size of audio data in bytes (0 for streaming).

    Returns:
        WAV header as bytes.
    """
    with io.BytesIO() as wav_io:
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            # For streaming, we don't write the data yet
        return wav_io.getvalue()[:44]  # Return just the header


def add_wav_header(
    audio_bytes: bytes,
    sample_rate: int,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Wrap audio bytes in a WAV container.

    Args:
        audio_bytes: Raw audio bytes.
        sample_rate: Sample rate in Hz.
        channels: Number of audio channels.
        sample_width: Bytes per sample.

    Returns:
        WAV file bytes with header.
    """
    with io.BytesIO() as wav_io:
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_bytes)
        return wav_io.getvalue()


def parse_wav(wav_bytes: bytes) -> Tuple[np.ndarray, int, int, int]:
    """Parse WAV bytes to extract audio data.

    Args:
        wav_bytes: WAV file bytes.

    Returns:
        Tuple of (audio_array, sample_rate, channels, sample_width).

    Raises:
        ValueError: If WAV file is invalid.
    """
    with io.BytesIO(wav_bytes) as wav_io:
        with wave.open(wav_io, "rb") as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
            audio = np.frombuffer(frames, dtype=np.int16)
            return audio, wav_file.getframerate(), wav_file.getnchannels(), wav_file.getsampwidth()


def validate_audio_format(
    audio: np.ndarray,
    expected_sample_rate: int,
    expected_channels: int = 1,
) -> bool:
    """Validate audio format matches expectations.

    Args:
        audio: Audio array.
        expected_sample_rate: Expected sample rate.
        expected_channels: Expected number of channels.

    Returns:
        True if format is valid, False otherwise.
    """
    # For now, just check if audio is valid numpy array
    # More detailed checks can be added
    if not isinstance(audio, np.ndarray):
        return False

    if audio.size == 0:
        return False

    return True


def chunk_audio(
    audio: np.ndarray,
    chunk_size_samples: int,
) -> list[np.ndarray]:
    """Split audio into fixed-size chunks.

    Args:
        audio: Input audio array.
        chunk_size_samples: Number of samples per chunk.

    Returns:
        List of audio chunks.
    """
    chunks = []
    for i in range(0, len(audio), chunk_size_samples):
        chunk = audio[i:i + chunk_size_samples]
        chunks.append(chunk)
    return chunks


def pad_audio_chunk(
    chunk: np.ndarray,
    target_size: int,
) -> np.ndarray:
    """Pad or trim audio chunk to target size.

    Args:
        chunk: Input audio chunk.
        target_size: Target number of samples.

    Returns:
        Padded or trimmed audio chunk.
    """
    current_size = len(chunk)

    if current_size == target_size:
        return chunk
    elif current_size < target_size:
        # Pad with zeros
        padding = np.zeros(target_size - current_size, dtype=chunk.dtype)
        return np.concatenate([chunk, padding])
    else:
        # Trim to size
        return chunk[:target_size]


class AudioConverter:
    """Utility class for audio format conversions.

    Provides high-level interface for converting between different
    audio formats and sample rates.
    """

    def __init__(
        self,
        input_sample_rate: int = 24000,
        output_sample_rate: int = 24000,
        output_format: str = "pcm_int16",
    ):
        """Initialize the audio converter.

        Args:
            input_sample_rate: Expected input sample rate.
            output_sample_rate: Target output sample rate.
            output_format: Output format (pcm_int16, pcm_float32, wav).
        """
        self.input_sample_rate = input_sample_rate
        self.output_sample_rate = output_sample_rate
        self.output_format = output_format

    def convert(
        self,
        audio: np.ndarray,
        normalize: bool = False,
    ) -> bytes:
        """Convert audio to output format.

        Args:
            audio: Input audio array (float32 or int16).
            normalize: Whether to normalize audio.

        Returns:
            Converted audio as bytes.
        """
        # Ensure float32
        if audio.dtype == np.int16:
            audio = int16_to_float32(audio)

        # Resample if needed
        if self.input_sample_rate != self.output_sample_rate:
            audio = resample(audio, self.input_sample_rate, self.output_sample_rate)

        # Normalize if requested
        if normalize:
            audio = normalize_audio(audio)

        # Convert to output format
        if self.output_format == "pcm_int16":
            result = int16_to_bytes(float32_to_int16(audio))
        elif self.output_format == "pcm_float32":
            result = float32_to_bytes(audio)
        elif self.output_format == "wav":
            pcm_bytes = int16_to_bytes(float32_to_int16(audio))
            result = add_wav_header(pcm_bytes, self.output_sample_rate)
        else:
            raise ValueError(f"Unknown output format: {self.output_format}")

        return result
