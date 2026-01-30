"""Speech-to-Text result dataclass."""

from dataclasses import dataclass


@dataclass
class TranscriptionResult:
    """Result from speech transcription.

    Attributes:
        text: Transcribed text
        is_final: Whether this is the final result
        confidence: Confidence score (0.0 to 1.0)
    """

    text: str
    is_final: bool
    confidence: float
