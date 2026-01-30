"""Constants for the voice client SDK."""

# =============================================================================
# Audio Constants
# =============================================================================
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_CHANNELS = 1
DEFAULT_BYTES_PER_SAMPLE = 2  # int16
OPTIMAL_CHUNK_SIZE = 4096  # bytes, ~85ms at 24kHz

# File format constants
WAV_RIFF_HEADER_SIZE = 12
WAV_RIFF_MAGIC = b"RIFF"
WAV_WAVE_MAGIC = b"WAVE"
MP3_ID3_MAGIC = b"ID3"
MP3_FRAME_MAGICS = (b"\xff\xfb", b"\xff\xfa", b"\xff\xff")
WAV_BYTES_PER_SAMPLE = 2  # 16-bit

# Chunking defaults
DEFAULT_CHUNK_MS = 80
SILENCE_THRESHOLD = 0.01
SILENCE_DURATION_MS = 1000

# =============================================================================
# Connection Constants
# =============================================================================
DEFAULT_WS_URL = "ws://localhost:16000/api/v1/ws"
DEFAULT_TIMEOUT = 30.0
RECONNECT_INITIAL_DELAY = 1.0
RECONNECT_MAX_DELAY = 30.0
HEARTBEAT_INTERVAL = 60.0
MESSAGE_LOOP_TIMEOUT = 1.0

# =============================================================================
# Supported Formats
# =============================================================================
SUPPORTED_SAMPLE_RATES = (16000, 24000)
SUPPORTED_CHANNELS = 1
SUPPORTED_BYTES_PER_SAMPLE = 2

# =============================================================================
# Type Aliases
# =============================================================================
AudioData = bytes
SampleRate = int
