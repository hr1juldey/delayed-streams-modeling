# Voice Server - Proposal

## Why

We need a production-ready FastAPI voice microservice server that provides real-time Speech-to-Text (STT) and Text-to-Speech (TTS) capabilities via WebSocket connections. The server will be consumed by an external DSPy + Ollama AI agent that orchestrates the conversation flow (audio→text→agent→text→audio). This enables voice-enabled AI assistants with low-latency streaming capabilities for local deployment on RTX 3060 GPUs (12GB VRAM shared with LLMs).

## What Changes

- Add `voice-server/` directory with complete FastAPI microservice
- Implement STT WebSocket endpoint using Kyutai STT models (1B-en_fr or 2.6b-en)
- Implement TTS WebSocket endpoint using Pocket TTS (100M params, CPU-only)
- Add voice management system (upload, list, switch, delete custom voices)
- Implement session management with history tracking and recovery
- Add health and metrics endpoints for monitoring
- Support both JSON and MessagePack protocols for WebSocket communication

## Capabilities

### New Capabilities
- `stt-websocket`: Real-time speech-to-text streaming via WebSocket using Kyutai STT models with configurable model selection, streaming modes (partial/final/both), and Voice Activity Detection (VAD)
- `tts-websocket`: Real-time text-to-speech streaming via WebSocket using Pocket TTS with voice parameter controls (speed, stability, pitch) and multiple audio output formats
- `voice-management`: Custom voice upload with auto-export to .safetensors format, voice listing, switching active voice, and voice deletion
- `session-management`: Session lifecycle management with server-generated UUID session IDs, conversation history storage (pluggable backends with SQLite default), client-provided history support, session recovery, and configurable timeout handling
- `audio-processing`: Audio format conversion (24kHz float32/int16 PCM, WAV chunks), resampling, normalization, and backpressure handling
- `websocket-protocol`: Bidirectional WebSocket communication supporting both JSON and MessagePack encoding with typed messages (Audio, Text, Error, Eos, Config)
- `monitoring`: Health check endpoint and Prometheus metrics endpoint for active sessions, request latency, and model status

### Modified Capabilities
- None (new standalone microservice)

## Impact

- **New directory**: `voice-server/` with complete FastAPI application
- **Dependencies**: fastapi, uvicorn, websockets, pydantic, msgpack, pocket-tts, moshi (Kyutai STT), torch, julius, sphn, prometheus-client, aiosqlite
- **GPU usage**: Kyutai STT uses GPU (configurable 1B or 2.6B model), Pocket TTS is CPU-only
- **Storage**: `data/voices/` for .safetensors voice files, `data/db/` for SQLite session storage
- **Ports**: Default port 16000 (16000 range for voice services), configurable via environment
- **Deployment**: Direct Python for development, Docker GPU-enabled for production (later phase)
