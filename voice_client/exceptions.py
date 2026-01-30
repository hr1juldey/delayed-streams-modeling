"""
Exception hierarchy for the Voice Client SDK.

Provides explicit exception types for different failure modes,
allowing users to catch and handle specific error conditions.
"""

from typing import Any


class VoiceClientError(Exception):
    """Base exception for all voice client errors.

    All exceptions raised by the voice client SDK inherit from this
    class, allowing users to catch all client errors with a single
    except clause:
        ```python
        try:
            await client.transcribe(audio)
        except VoiceClientError as e:
            print(f"Voice client error: {e}")
        ```
    """

    def __init__(self, message: str, *args: Any) -> None:
        self.message = message
        super().__init__(message, *args)


class ConnectionError(VoiceClientError):
    """Connection failed or lost.

    Raised when:
    - Initial connection to the WebSocket server fails
    - Connection is lost during operation
    - Reconnection attempts are exhausted
    """

    pass


class AudioFormatError(VoiceClientError):
    """Audio format validation failed.

    Raised when:
    - Audio file format is not supported (e.g., MP3 without conversion)
    - Sample rate is not 16000 or 24000 Hz
    - Audio has more than 1 channel
    - Bit depth is not 16-bit
    - Audio file does not exist or cannot be read

    The error message includes actionable guidance for fixing the issue.
    """

    pass


class ProtocolError(VoiceClientError):
    """Message protocol error.

    Raised when:
    - Invalid JSON is received
    - Invalid MessagePack is received
    - Unknown message type is encountered
    - Message encoding/decoding fails
    """

    pass


class ConfigurationError(VoiceClientError):
    """Invalid configuration.

    Raised when:
    - Invalid configuration parameters are provided
    - Required configuration is missing
    - Configuration values are out of range
    """

    pass


class TimeoutError(VoiceClientError):
    """Operation timed out.

    Raised when:
    - Transcription does not complete within the timeout period
    - Synthesis does not produce audio within the timeout period
    - Connection attempt times out
    """

    pass


class ServerError(VoiceClientError):
    """Server returned an error.

    Raised when the voice server returns an ERROR message.
    Includes the server's error code and details.
    """

    def __init__(self, message: str, code: str | None = None, details: str | None = None) -> None:
        self.code = code
        self.details = details
        super().__init__(message)

    def __str__(self) -> str:
        parts = [self.message]
        if self.code:
            parts.append(f"Code: {self.code}")
        if self.details:
            parts.append(f"Details: {self.details}")
        return " | ".join(parts)


class RecordingError(VoiceClientError):
    """Audio recording failed.

    Raised when:
    - Microphone access is denied
    - Audio device is not available
    - Recording operation fails
    """

    pass


class PlaybackError(VoiceClientError):
    """Audio playback failed.

    Raised when:
    - Audio output device is not available
    - Playback operation fails
    - Invalid audio data is provided for playback
    """

    pass
