"""Text-to-Speech audio chunk dataclass."""

from dataclasses import dataclass


@dataclass
class AudioChunk:
    """Audio chunk from TTS synthesis.

    Attributes:
        data: Raw audio data
        format: Audio format (e.g., "pcm_int16")
        sample_rate: Sample rate in Hz
        is_final: Whether this is the final chunk
    """

    data: bytes
    format: str
    sample_rate: int
    is_final: bool
