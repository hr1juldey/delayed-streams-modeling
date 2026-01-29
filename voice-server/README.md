# Voice Server

A production-ready FastAPI voice microservice server providing real-time Speech-to-Text (STT) and Text-to-Speech (TTS) capabilities via WebSocket connections.

## Features

- **STT WebSocket**: Real-time speech-to-text using Kyutai STT models (1B-en_fr or 2.6b-en)
- **TTS WebSocket**: Real-time text-to-speech using Pocket TTS (CPU-only, ~6x real-time)
- **Voice Management**: Upload, list, switch, and delete custom voices
- **Session Management**: Track sessions with history, recovery, and configurable timeouts
- **Monitoring**: Health checks and Prometheus metrics

## Quick Start

### Installation

```bash
# Clone the repository
cd delayed-streams-modeling/voice-server

# Install dependencies
pip install -e .

# Or using uv
uv pip install -e .
```

### Configuration

Copy `.env.example` to `.env` and configure as needed:

```bash
cp .env.example .env
# Edit .env with your settings
```

### Running the Server

#### Development

```bash
# Using uvicorn directly
uvicorn src.main:app --host 0.0.0.0 --port 16000 --reload

# Or using the dev script
./scripts/start_dev.sh
```

#### Production

```bash
# Using the prod script
./scripts/start_prod.sh

# Or with Docker (when ready)
docker run --gpus all -v ./data:/app/data -p 16000:16000 voice-server:latest
```

## API Endpoints

### WebSocket Endpoints

#### STT WebSocket: `/api/v1/ws/stt`

Real-time speech-to-text streaming.

**Message Types:**
- `Audio` - Input audio chunks (PCM float32 or int16)
- `Text` - Transcription results (partial or final)
- `Error` - Error messages
- `EOS` - End of stream marker
- `Config` - Session configuration

**Connection:**

```python
import websockets
import msgpack

async with websockets.connect("ws://localhost:16000/api/v1/ws/stt") as ws:
    # Send config
    await ws.send(msgpack.packb({
        "type": "Config",
        "data": {"streaming_mode": "both", "vad_mode": "client"},
        "session_id": None
    }))

    # Send audio
    await ws.send(msgpack.packb({
        "type": "Audio",
        "data": [float32_samples...],
        "session_id": session_id
    }))

    # Receive transcription
    response = msgpack.unpackb(await ws.recv())
```

#### TTS WebSocket: `/api/v1/ws/tts`

Real-time text-to-speech streaming.

**Connection:**

```python
import websockets
import msgpack

async with websockets.connect("ws://localhost:16000/api/v1/ws/tts") as ws:
    # Send config
    await ws.send(msgpack.packb({
        "type": "Config",
        "data": {"output_format": "pcm_int16", "voice": "default"},
        "session_id": None
    }))

    # Send text
    await ws.send(msgpack.packb({
        "type": "Text",
        "data": "Hello, world!",
        "session_id": session_id
    }))

    # Receive audio
    while True:
        response = msgpack.unpackb(await ws.recv())
        if response["type"] == "Audio":
            # Play audio chunk
            ...
        elif response["type"] == "EOS":
            break
```

### HTTP Endpoints

#### Health: `/health`

```bash
curl http://localhost:16000/health
```

#### Metrics: `/metrics` (Prometheus format)

```bash
curl http://localhost:16000/metrics
```

#### Voice Management

- `POST /api/v1/voice/upload` - Upload voice audio file
- `GET /api/v1/voice/list` - List available voices
- `POST /api/v1/voice/switch` - Switch active voice
- `DELETE /api/v1/voice/{voice_id}` - Delete voice
- `GET /api/v1/voice/{voice_id}` - Get voice metadata

## Configuration

Key environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `VOICE_SERVER__PORT` | 16000 | Server port |
| `VOICE_SERVER__STT__MODEL_NAME` | 1b-en_fr | STT model (1b-en_fr or 2.6b-en) |
| `VOICE_SERVER__STT__DEVICE` | cuda | STT device (cuda/cpu) |
| `VOICE_SERVER__TTS__DEFAULT_VOICE` | default | Default TTS voice |
| `VOICE_SERVER__MAX_CONCURRENT_SESSIONS` | 10 | Max concurrent sessions |
| `VOICE_SERVER__VOICES_PATH` | ./data/voices | Voice storage path |

See `.env.example` for all available options.

## Examples

See the `examples/` directory for test clients:

- `stt_client.py` - STT WebSocket test client
- `tts_client.py` - TTS WebSocket test client
- `full_conversation.py` - Complete STT + TTS flow

## Architecture

```
voice-server/
├── config/          # Configuration settings
├── src/
│   ├── main.py      # FastAPI application
│   ├── api/routes/  # API endpoints
│   ├── core/        # Core functionality
│   ├── models/      # STT and TTS models
│   ├── services/    # Business logic
│   └── utils/       # Utilities
├── tests/           # Tests
├── examples/        # Test clients
└── data/            # Voices and database
```

## Hardware Requirements

- **GPU**: RTX 3060 12GB or better for STT (2-3GB VRAM for 1B model)
- **CPU**: Any modern CPU for TTS (Pocket TTS is CPU-only)
- **RAM**: 8GB+ recommended

## Performance

- **STT Latency**: <200ms for first token
- **TTS Speed**: ~6x faster than real-time
- **Concurrent Sessions**: Up to 10 (configurable)

## License

This project is part of the Kyutai delayed-streams-modeling repository.
