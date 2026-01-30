## Why

The current voice server example clients are error-prone and difficult to use correctly. Users must manually implement:
- WAV header parsing and audio validation
- Base64 encoding for JSON messages
- Optimal audio chunk sizing
- Session management and cleanup
- Reconnection with exponential backoff
- Proper error handling and recovery

This leads to common mistakes: incorrect audio formats, forgotten message encoding, resource leaks, and brittle error handling. A dedicated client SDK with preconfigured defaults, automatic validation, and graceful error handling would significantly improve developer experience and reduce integration issues.

## What Changes

- **Create new `voice_client/` package** as a sibling to `voice_server/`
- **STTClient**: Speech-to-Text client with automatic audio handling, validation, and streaming
- **TTSClient**: Text-to-Speech client with streaming audio output
- **VoiceClient**: Combined STT + TTS client for full conversations
- **AudioHandler**: File-based audio I/O (WAV parsing, validation, chunking)
- **AudioRecorder/AudioPlayer**: Device-based audio I/O (microphone recording, playback)
- **Protocol layer**: Message types and encoders (JSON/MessagePack) matching server
- **Exception hierarchy**: Explicit error types for different failure scenarios
- **Auto-reconnection**: Exponential backoff reconnection logic
- **Context managers**: `async with` support for automatic cleanup

## Capabilities

### New Capabilities

- `stt-client`: Speech-to-Text WebSocket client for transcribing audio
  - Accepts file paths or raw audio bytes
  - Automatic audio format validation (sample rate, channels, bit depth)
  - Configurable chunk size with optimal defaults
  - Streaming and one-shot transcription modes
  - Automatic session management

- `tts-client`: Text-to-Speech WebSocket client for synthesizing speech
  - Stream audio chunks as they're generated
  - Save to file or return complete audio
  - Configurable voice, format, and synthesis options
  - Automatic session management

- `voice-client`: Combined STT + TTS client for conversations
  - Full conversation flow: transcribe → process → synthesize
  - Pluggable agent callback for response generation
  - Simplified API for common use cases

- `audio-io`: Audio recording and playback capabilities
  - Microphone recording with silence detection
  - Low-latency audio playback
  - Device enumeration and selection
  - Async streaming interfaces

- `websocket-protocol`: Client-side WebSocket protocol implementation
  - Message types matching server (Audio, Text, Error, EOS, Config)
  - JSON and MessagePack encoding support
  - Base64 audio encoding for JSON mode
  - Message validation and error handling

### Modified Capabilities

None. This is a new standalone client package that interfaces with the existing voice server WebSocket API. No existing server capabilities are being modified.

## Impact

**New Code:**
- `voice_client/` package with ~8 core modules
- Example scripts demonstrating usage patterns
- Optional: Unit and integration tests

**Dependencies:**
- Required: `websockets>=14.0`, `sounddevice>=0.4.6`, `numpy>=1.20.0`
- Optional: `msgpack>=1.0.0` for binary encoding
- Standard library: `asyncio`, `dataclasses`, `wave`, `base64`, `uuid`, `pathlib`, `enum`, `typing`

**Distribution:**
- Initially copy-paste within the repo
- Can be packaged as PyPI (`voice-client-sdk`) later

**API Changes:**
- No breaking changes to existing code
- New optional client SDK for easier integration
- Existing WebSocket API remains unchanged
