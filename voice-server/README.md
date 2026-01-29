# Voice Server

A production-ready FastAPI voice microservice server providing real-time Speech-to-Text (STT) and Text-to-Speech (TTS) capabilities via WebSocket connections.

## Features

- **STT WebSocket**: Real-time speech-to-text using Kyutai STT models (1B-en_fr or 2.6B-en)
  - Streaming transcription with partial and final results
  - Server-side VAD (Voice Activity Detection) support
  - Timestamp extraction for word-level timing
  - Model switching without server restart

- **TTS WebSocket**: Real-time text-to-speech using Pocket TTS
  - CPU-only, thread-safe processing (~6x real-time speed)
  - Multiple output formats (int16, float32, WAV)
  - Voice parameter controls (speed, stability, pitch)
  - Custom voice support

- **Voice Management**: Upload, list, switch, and delete custom voices

- **Session Management**:
  - Server-generated UUID session IDs
  - Session history tracking with SQLite persistence
  - Configurable timeouts and cleanup
  - Client-provided history support

- **Monitoring**:
  - `/health` endpoint with status and model information
  - `/metrics` endpoint with Prometheus metrics
  - Built-in heartbeat monitoring

## Quick Start

### Installation

```bash
# Navigate to the voice-server directory
cd delayed-streams-modeling/voice-server

# Install dependencies
pip install -e .

# Or using uv
uv pip install -e .
```

**Dependencies:**
- `fastapi>=0.115.0` - Web framework
- `uvicorn[standard]>=0.32.0` - ASGI server
- `websockets>=14.0` - WebSocket support
- `moshi==0.2.11` - Kyutai STT model
- `pocket-tts` - CPU-only TTS model
- `torch` - GPU support (CUDA recommended)
- `julius` - Audio resampling
- `aiosqlite>=0.20.0` - Async SQLite
- `prometheus-client>=0.21.0` - Metrics

### Configuration

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Key configuration options:

```bash
# Server
VOICE_SERVER__HOST=0.0.0.0
VOICE_SERVER__PORT=16000
VOICE_SERVER__API_KEYS=["your-api-key-here"]  # Optional authentication
VOICE_SERVER__MAX_CONCURRENT_SESSIONS=10

# STT (Speech-to-Text)
VOICE_SERVER__STT__MODEL_NAME=1b-en_fr  # Options: 1b-en_fr, 2.6b-en
VOICE_SERVER__STT__DEVICE=cuda  # or cpu
VOICE_SERVER__STT__PRELOAD_MODEL=true  # Load on startup
VOICE_SERVER__STT__VAD_MODE=client  # Options: client, server
VOICE_SERVER__STT__STREAMING_MODE=both  # Options: partial, final, both

# TTS (Text-to-Speech)
VOICE_SERVER__TTS__DEFAULT_VOICE=default
VOICE_SERVER__TTS__DEVICE=cpu  # Pocket TTS is CPU-only
VOICE_SERVER__TTS__PRELOAD_MODEL=true
VOICE_SERVER__TTS__SPEED=1.0  # 0.5 to 2.0
VOICE_SERVER__TTS__STABILITY=1.0  # 0.0 to 1.0
VOICE_SERVER__TTS__PITCH=1.0  # 0.5 to 2.0

# Storage
VOICE_SERVER__VOICES_PATH=./data/voices
VOICE_SERVER__DB_PATH=./data/db
```

### Running the Server

#### Development Mode

```bash
# Using uvicorn directly
uvicorn src.main:app --host 0.0.0.0 --port 16000 --reload

# Or using the dev script
./scripts/start_dev.sh
```

#### Production Mode

```bash
# Using the prod script
./scripts/start_prod.sh

# Or with uvicorn (no reload)
uvicorn src.main:app --host 0.0.0.0 --port 16000 --workers 1
```

The server will be available at:
- API Docs: http://localhost:16000/docs
- Health: http://localhost:16000/health
- Metrics: http://localhost:16000/metrics
- STT WebSocket: `ws://localhost:16000/api/v1/ws/stt`
- TTS WebSocket: `ws://localhost:16000/api/v1/ws/tts`

## API Documentation

### WebSocket Endpoints

#### STT WebSocket: `/api/v1/ws/stt`

Real-time speech-to-text streaming.

**Authentication:**
- Query parameter: `?api_key=YOUR_KEY`
- Header: `Authorization: Bearer YOUR_KEY`

**Connection URL:**
```
ws://localhost:16000/api/v1/ws/stt?encoding=json
```

**Message Protocol:**

All messages are JSON objects with the following structure:

```json
{
  "type": "MessageType",
  "data": <payload>,
  "session_id": "uuid"
}
```

**Message Types:**

| Type | Direction | Description |
|------|-----------|-------------|
| `Config` | Client→Server | Configure session options |
| `Audio` | Client→Server | Send audio chunk |
| `Text` | Server→Client | Transcription result |
| `Error` | Server→Client | Error message |
| `Eos` | Both | End of stream marker |
| `Heartbeat` | Both | Ping/Pong for keep-alive |

**Config Message:**
```json
{
  "type": "Config",
  "data": {
    "streaming_mode": "both",  // "partial", "final", or "both"
    "vad_mode": "client",       // "client" or "server"
    "input_format": "int16"     // "int16", "float32", or "wav"
  },
  "session_id": "my-session"
}
```

**Audio Message:**
```json
{
  "type": "Audio",
  "data": "<base64_encoded_audio_bytes>",
  "session_id": "my-session"
}
```

**Text Response:**
```json
{
  "type": "Text",
  "data": "transcribed text here",
  "session_id": "server-uuid",
  "is_partial": false,
  "is_final": true,
  "confidence": 0.95
}
```

**EOS Message:**
```json
{
  "type": "Eos",
  "data": null,
  "session_id": "my-session",
  "reason": "transcription_complete"
}
```

#### TTS WebSocket: `/api/v1/ws/tts`

Real-time text-to-speech streaming.

**Connection URL:**
```
ws://localhost:16000/api/v1/ws/tts?encoding=json
```

**Config Message:**
```json
{
  "type": "Config",
  "data": {
    "voice_id": "default",
    "output_format": "pcm_int16",  // "pcm_int16", "pcm_float32", or "wav"
    "streaming": true
  },
  "session_id": "my-session"
}
```

**Text Message:**
```json
{
  "type": "Text",
  "data": "Hello, world!",
  "session_id": "my-session"
}
```

**Audio Response:**
```json
{
  "type": "Audio",
  "data": "<base64_encoded_audio_bytes>",
  "session_id": "server-uuid",
  "format": "pcm_int16",
  "sample_rate": 24000,
  "channels": 1
}
```

### HTTP Endpoints

#### Health Check: `/health`

Get server status and model information.

```bash
curl http://localhost:16000/health
```

Response:
```json
{
  "status": "ok",
  "timestamp": 1234567890.123,
  "models": {
    "stt": {
      "is_initialized": true,
      "model_name": "1b-en_fr",
      "device": "cuda",
      "active_sessions": 2
    },
    "tts": {
      "is_initialized": true,
      "model_name": "pocket",
      "voice_id": "default"
    }
  },
  "sessions": {
    "active_websockets": 3,
    "active_sessions": 2
  }
}
```

#### Metrics: `/metrics`

Prometheus-style metrics.

```bash
curl http://localhost:16000/metrics
```

Available metrics:
- `voice_server_active_sessions` - Active STT/TTS sessions
- `voice_server_stt_request_latency_ms` - STT request latency
- `voice_server_tts_request_latency_ms` - TTS request latency
- `voice_server_model_status` - Model loaded status
- `voice_server_errors_total` - Error count
- `voice_server_websocket_connections_total` - Connection count
- `voice_server_audio_bytes_total` - Audio processed

#### Voice Management

**List Voices:**
```bash
curl http://localhost:16000/api/v1/voice/list
```

**Switch Voice:**
```bash
curl -X POST http://localhost:16000/api/v1/voice/switch \
  -H "Content-Type: application/json" \
  -d '{"voice_id": "custom_voice"}'
```

**Set Voice Parameters:**
```bash
curl -X POST http://localhost:16000/api/v1/voice/parameters \
  -H "Content-Type: application/json" \
  -d '{"speed": 1.2, "stability": 0.8, "pitch": 1.0}'
```

**Upload Voice:**
```bash
curl -X POST http://localhost:16000/api/v1/voice/upload \
  -F "file=@voice_sample.wav" \
  -F "voice_id=my_custom_voice" \
  -F "description=My custom voice"
```

**Delete Voice:**
```bash
curl -X DELETE http://localhost:16000/api/v1/voice/my_custom_voice
```

## Examples

The `examples/` directory contains test clients:

### STT Client

Test speech-to-text with an audio file:

```bash
python examples/stt_client.py audio_sample.wav
```

With options:
```bash
python examples/stt_client.py audio_sample.wav \
  --url ws://localhost:16000/api/v1/ws/stt \
  --api-key YOUR_KEY \
  --encoding json
```

### TTS Client

Test text-to-speech synthesis:

```bash
python examples/tts_client.py "Hello, world!" --output response.wav
```

With options:
```bash
python examples/tts_client.py "Hello, world!" \
  --url ws://localhost:16000/api/v1/ws/tts \
  --voice default \
  --format wav \
  --output response.wav
```

### Full Conversation Example

Demonstrates complete STT → Agent → TTS flow:

```bash
python examples/full_conversation.py user_input.wav \
  --response "I heard you say: {user_input}" \
  --output agent_response.wav
```

This example shows how to:
1. Connect to both STT and TTS endpoints
2. Transcribe user speech
3. Process with an agent (placeholder for your AI)
4. Synthesize the response
5. Handle the full conversation flow

## Hardware Requirements

- **GPU**: RTX 3060 12GB or better for STT
  - 1B-en_fr model: ~2-3GB VRAM
  - 2.6B-en model: ~5-6GB VRAM
- **CPU**: Any modern CPU for TTS (Pocket TTS is CPU-only)
- **RAM**: 8GB+ recommended
- **Storage**: ~500MB for models + voice files

## Performance

- **STT Latency**:
  - First token: <200ms
  - Streaming: ~80ms chunk size
  - Model loading: ~5 seconds (cold start)

- **TTS Speed**:
  - ~6x faster than real-time
  - 10 seconds of speech → ~1.7 seconds processing

- **Concurrent Sessions**:
  - Up to 10 simultaneous sessions (configurable)
  - TTS uses thread-safe worker pattern

## Project Structure

```
voice-server/
├── config/                  # Configuration
│   ├── __init__.py
│   ├── settings.py          # Pydantic Settings
│   └── logging_config.py    # Logging setup
├── src/
│   ├── main.py              # FastAPI app entry point
│   ├── api/
│   │   ├── dependencies.py   # Auth, session deps
│   │   ├── middleware.py     # Rate limiting
│   │   └── routes/
│   │       ├── health.py     # /health, /metrics
│   │       ├── voice.py      # Voice management
│   │       ├── websocket_stt.py   # STT WebSocket
│   │       └── websocket_tts.py   # TTS WebSocket
│   ├── core/
│   │   ├── exceptions.py     # Custom exceptions
│   │   ├── lifecycle.py      # Startup/shutdown
│   │   └── security.py       # API key auth
│   ├── models/
│   │   ├── stt/             # STT models
│   │   │   ├── base.py       # STTModelBase
│   │   │   ├── kyutai.py     # KyutaiSTTModel
│   │   │   └── model_manager.py
│   │   └── tts/             # TTS models
│   │       ├── base.py       # TTSModelBase
│   │       ├── pocket.py     # PocketTTSModel
│   │       ├── worker.py     # Thread-safe TTSWorker
│   │       └── model_manager.py
│   ├── services/
│   │   ├── audio/           # Audio processing
│   │   │   ├── processor.py  # Format conversion
│   │   │   ├── buffer.py     # Backpressure handling
│   │   │   └── vad.py        # Voice Activity Detection
│   │   ├── session/          # Session management
│   │   │   ├── models.py     # Session data models
│   │   │   ├── store.py      # SQLite + InMemory stores
│   │   │   └── manager.py    # SessionManager
│   │   └── websocket/       # WebSocket utilities
│   │       ├── protocol.py   # Message protocol
│   │       ├── connection.py # ConnectionManager
│   │       ├── heartbeat.py  # Heartbeat monitoring
│   │       └── routing.py    # Session routing
│   └── utils/
│       ├── audio.py          # Audio utilities
│       └── metrics.py        # Prometheus metrics
├── tests/                    # Tests
├── examples/                 # Test clients
│   ├── stt_client.py
│   ├── tts_client.py
│   └── full_conversation.py
├── scripts/                  # Startup scripts
│   ├── start_dev.sh
│   └── start_prod.sh
├── data/                     # Runtime data
│   ├── voices/               # Custom voice files
│   └── db/                   # SQLite database
├── .env.example              # Configuration template
├── pyproject.toml            # Project dependencies
└── README.md
```

## Session Management

The server generates unique session IDs (UUIDs) for each connection. Sessions can:

- **Resume**: Use the same session_id to resume (if not expired)
- **History**: Track conversation turns in SQLite
- **Timeout**: Automatically close after inactivity (configurable)
- **Limits**: Enforce maximum concurrent sessions

## Troubleshooting

### STT Model Not Loading

```bash
# Check CUDA availability
python -c "import torch; print(torch.cuda.is_available())"

# Check moshi installation
python -c "import moshi; print(mosi.__version__)"
```

### TTS Not Working

Pocket TTS is CPU-only. Make sure:
```bash
python -c "import pocket_tts; print('OK')"
```

### WebSocket Connection Issues

Check that:
1. Server is running: `curl http://localhost:16000/health`
2. Correct URL format: `ws://localhost:16000/api/v1/ws/stt`
3. API key if required

## License

This project is part of the Kyutai delayed-streams-modeling repository.
