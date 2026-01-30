"""Audio I/O for microphone recording and speaker playback."""

from voice_client.audio_io.player import AudioPlayer
from voice_client.audio_io.recorder import AudioRecorder

__all__ = ["AudioPlayer", "AudioRecorder"]
