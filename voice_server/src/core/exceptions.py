"""Custom exception classes for the voice server."""


class VoiceServerException(Exception):
    """Base exception for voice server errors."""

    def __init__(self, message: str, code: str = "VOICE_SERVER_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(self.message)


class AuthenticationException(VoiceServerException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, code="AUTHENTICATION_ERROR")


class SessionException(VoiceServerException):
    """Raised when session management fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="SESSION_ERROR")


class ModelException(VoiceServerException):
    """Raised when model operations fail."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="MODEL_ERROR")


class AudioProcessingException(VoiceServerException):
    """Raised when audio processing fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="AUDIO_PROCESSING_ERROR")


class VoiceException(VoiceServerException):
    """Raised when voice operations fail."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="VOICE_ERROR")
