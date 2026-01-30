"""Speech-to-Text (STT) client for the voice server."""

from voice_client.stt.client import STTClient
from voice_client.stt.result import TranscriptionResult

__all__ = ["STTClient", "TranscriptionResult"]
