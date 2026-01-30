## Context

### Background

The voice server provides WebSocket endpoints for Speech-to-Text (STT) and Text-to-Speech (TTS) but has no official client SDK. Current example clients (`stt_client.py`, `full_conversation.py`) are error-prone and require users to manually implement:

- WAV header parsing and audio format validation
- Base64 encoding for JSON messages
- Optimal audio chunk sizing
- Session management and cleanup
- Reconnection with exponential backoff
- Proper error handling and recovery

### Current State

- Voice server WebSocket API is functional but requires expert knowledge to use correctly
- Example clients exist but contain hardcoded values and lack error handling
- No validation of audio formats, sample rates, or chunk sizes
- No reconnection logic or resilience features
- Users must manually construct WebSocket messages, leading to common mistakes

### Constraints

- **Minimal dependencies**: Use only `websockets` + standard library where possible
- **Python 3.9+ compatibility**: Required for type hint syntax (`dict | None`)
- **Async/await**: All I/O operations must be async
- **Sounddevice for audio I/O**: Selected over PyAudio for easier cross-platform support
- **Copy-paste distribution**: Initial distribution within repo, PyPI packaging later

### Stakeholders

- **Voice server users**: Developers integrating STT/TTS into their applications
- **Voice server maintainers**: Reduced support burden from user errors
- **End users**: More reliable voice applications due to better error handling

---

## Goals / Non-Goals

**Goals:**

1. Provide a "just works" client SDK with sensible defaults
2. Validate all inputs early with clear error messages
3. Handle WebSocket connection lifecycle automatically (connect, reconnect, disconnect)
4. Support both JSON and MessagePack encoding modes
5. Provide both file-based and device-based audio I/O
6. Enforce proper resource cleanup via context managers
7. Type-safe API with comprehensive type hints

**Non-Goals:**

1. Audio format conversion (e.g., MP3 → WAV) - users must pre-convert
2. Multi-language support in client (server handles language detection)
3. Batch processing of multiple audio files (single session per request)
4. Synchronous/blocking API variants (async-only for consistency)
5. Built-in agent/AI integration (client provides callback hooks only)
6. Recording/playback of non-PCM audio formats

---

## Decisions

### D1: Async Context Managers for Connection Lifecycle

**Decision:** Use `async with` for all client connections.

**Rationale:**
- Ensures automatic cleanup even when exceptions occur
- Python's context manager protocol is well-understood
- Forces users to properly scope connections
- Eliminates resource leaks from forgotten `close()` calls

**Alternatives considered:**
- Explicit `connect()`/`disconnect()` methods: More flexible but error-prone
- Reference counting with `__del__`: Non-deterministic cleanup

### D2: Separate STT/TTS Client Classes

**Decision:** Create separate `STTClient` and `TTSClient` classes with `VoiceClient` combining both.

**Rationale:**
- Users may only need one capability (STT-only or TTS-only)
- Smaller API surface for single-use cases
- Clear separation of concerns
- `VoiceClient` provides convenience for combined use

**Alternatives considered:**
- Single monolithic client: Larger API, more complex
- Composition only (no combined class): Less convenient for common use case

### D3: Audio Format Validation on Load

**Decision:** Validate audio format immediately when file/bytes are provided, before sending to server.

**Rationale:**
- Fail fast with clear error messages
- Avoid wasting bandwidth on invalid audio
- Provide actionable error messages (e.g., "convert with ffmpeg ...")
- Server can assume valid input from SDK users

**Alternatives considered:**
- Let server validate: Delayed feedback, harder to debug
- Lazy validation on send: Less predictable error timing

### D4: Optimal Chunk Size of 4096 bytes (~85ms at 24kHz)

**Decision:** Use 4096 bytes as default chunk size.

**Rationale:**
- Balances latency and throughput (based on research from Deepgram, ElevenLabs)
- 4096 bytes = ~85ms at 24kHz int16 (2 bytes/sample × 24000 samples/s × 0.085s)
- Smaller chunks = more overhead, larger chunks = higher latency
- Can be overridden if needed via `chunk_size_ms` parameter

**Alternatives considered:**
- User-specified chunk size: Burdens user to know optimal value
- Adaptive chunking based on network: More complex, unpredictable

### D5: Base64 for JSON, Raw Bytes for MessagePack

**Decision:** Automatically base64-encode audio data in JSON mode, send raw bytes in MessagePack mode.

**Rationale:**
- JSON cannot encode binary data directly
- MessagePack natively supports binary frames
- Transparency to user - encoding mode parameter controls behavior
- Matches server-side protocol

**Alternatives considered:**
- Always use base64: Unnecessary overhead for MessagePack
- Always use MessagePack: JSON is more debuggable for development

### D6: Exponential Backoff Reconnection

**Decision:** Implement exponential backoff reconnection with 1s initial delay and 30s max delay.

**Rationale:**
- Prevents server flooding during outages
- Industry standard for WebSocket clients
- `websockets` library has built-in support via environment variables
- Balances responsiveness with server stability

**Alternatives considered:**
- Immediate retry: Can overwhelm server
- Fixed delay: Either too slow (large delay) or too aggressive (small delay)
- No reconnection: Poor user experience

### D7: sounddevice over PyAudio

**Decision:** Use `sounddevice` library for audio recording/playback.

**Rationale:**
- Fewer installation issues than PyAudio
- Better NumPy integration
- Simpler API for basic operations
- Cross-platform support (Windows, macOS, Linux)

**Alternatives considered:**
- PyAudio: Complex installation on some platforms
- Platform-specific commands: Not cross-platform
- No built-in audio I/O: Forces users to implement themselves

### D8: Dataclasses over Pydantic for Messages

**Decision:** Use standard `@dataclass` for message types, not Pydantic models.

**Rationale:**
- Zero runtime validation overhead (Pydantic adds cost)
- Simpler dependency profile
- Sufficient for this use case (messages validated on encode/decode)
- Python 3.9+ dataclasses support type hints well

**Alternatives considered:**
- Pydantic: More validation, but adds dependency and runtime cost
- TypedDict: Less feature-rich (no methods, no default values in some cases)

### D9: Message Handler Registration Pattern

**Decision:** Use `on_message(msg_type, handler)` for registering message callbacks.

**Rationale:**
- Flexible - users can add custom handlers
- Decouples message handling from connection logic
- Allows multiple handlers per message type
- Standard pattern in async WebSocket libraries

**Alternatives considered:**
- Inheritance with abstract methods: Less flexible, more boilerplate
- Single callback per client: Harder to extend

### D10: Exception Hierarchy

**Decision:** Create explicit exception types for different failure modes (ConnectionError, AudioFormatError, ProtocolError, etc.).

**Rationale:**
- Users can catch specific error types
- Enables different recovery strategies per error type
- More actionable error messages
- Standard practice in SDK design

**Alternatives considered:**
- Single exception type: Less informative, harder to handle selectively

---

## Risks / Trade-offs

### R1: sounddevice Installation Complexity

**Risk:** `sounddevice` requires PortAudio, which can have installation issues on some platforms.

**Mitigation:** Provide clear installation instructions in documentation, fallback to file-only mode if sounddevice unavailable.

### R2: WebSocket Server Compatibility

**Risk:** Client may break if server WebSocket API changes.

**Mitigation:** Version the client alongside server, maintain protocol compatibility layer, add integration tests.

### R3: Async Complexity for Beginners

**Risk:** Async/await may be difficult for Python beginners.

**Mitigation:** Provide comprehensive examples, clear documentation of common patterns, synchronous wrappers where appropriate.

### R4: Audio Device Fragmentation

**Risk:** Different systems have different audio devices and configurations.

**Mitigation:** Provide device enumeration methods (`AudioRecorder.list_devices()`), use system defaults where possible, document device selection.

### R5: Memory Usage for Large Audio Files

**Risk:** Loading entire audio files into memory may be problematic for very large files.

**Mitigation:** Document file size recommendations, implement streaming interface for large files, consider chunked file reading in future.

### T1: MessagePack vs JSON Trade-off

**Trade-off:** MessagePack is more efficient but less human-readable for debugging.

**Resolution:** Default to JSON (more debuggable), allow MessagePack via parameter for production use.

### T2: Chunk Size vs Latency Trade-off

**Trade-off:** Smaller chunks reduce latency but increase overhead. Larger chunks reduce overhead but increase latency.

**Resolution:** Use research-backed 4096 bytes (~85ms) as optimal default, allow override for advanced users.

### T3: Reconnection vs Fresh Start Trade-off

**Trade-off:** Reconnection preserves state but may replay operations. Fresh start is simpler but loses context.

**Resolution:** Auto-reconnect for transient failures, require new client object for intentional restarts.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Voice Client SDK                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────┐    ┌───────────────────┐    ┌──────────────────┐│
│  │   STTClient       │    │   TTSClient       │    │  VoiceClient     ││
│  │  (Speech-to-Text) │    │  (Text-to-Speech) │    │  (STT + TTS)     ││
│  └────────┬──────────┘    └────────┬──────────┘    └────────┬─────────┘│
│           │                        │                        │           │
│           └────────────────────────┴────────────────────────┘           │
│                                    │                                    │
│                           ┌────────▼────────┐                          │
│                           │  BaseClient     │                          │
│                           │  - Connection   │                          │
│                           │  - Protocol     │                          │
│                           │  - Reconnect    │                          │
│                           └────────┬────────┘                          │
│                                    │                                    │
│  ┌─────────────────────────────────┼─────────────────────────────────┐ │
│  │                                 │                                 │ │
│  │  ┌──────────────┐  ┌──────────┐ │ ┌──────────┐  ┌──────────────┐ │ │
│  │  │ AudioHandler │  │Protocol  │ │ │Validator │  │ ErrorHandler │ │ │
│  │  │ - WAV parse  │  │- encode  │ │ │- configs │  │- exceptions │ │ │
│  │  │ - validation │  │- decode  │ │ │- audio   │  │- recovery   │ │ │
│  │  │ - chunking   │  │- types   │ │ │- messages│  │- logging    │ │ │
│  │  └──────────────┘  └──────────┘ │ └──────────┘  └──────────────┘ │ │
│  │                                    │                                 │ │
│  │  ┌──────────────┐                  │                                 │ │
│  │  │AudioRecorder │  │AudioPlayer│   │                                 │ │
│  │  │ - mic input  │  │ - output  │   │                                 │ │
│  │  │ - silence    │  │ - stream  │   │                                 │ │
│  │  └──────────────┘  └──────────┘   │                                 │ │
│  └────────────────────────────────────┘                                 │
│                                                                         │
│  Dependencies: websockets + sounddevice + standard library                │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Summary

| Component | Responsibility | Key Methods |
|-----------|---------------|-------------|
| `BaseClient` | WebSocket connection, reconnection, message loop | `connect()`, `disconnect()`, `send()` |
| `STTClient` | Speech-to-Text transcription | `transcribe()`, `send_audio()`, `stream_transcription()` |
| `TTSClient` | Text-to-Speech synthesis | `synthesize()`, `synthesize_full()`, `synthesize_to_file()` |
| `VoiceClient` | Combined STT + TTS conversations | `converse()` |
| `AudioHandler` | File-based audio I/O | `load_audio_file()`, `chunk_audio()` |
| `AudioRecorder` | Microphone recording | `record()`, `record_stream()` |
| `AudioPlayer` | Audio playback | `play()`, `play_async()`, `play_stream()` |
| `MessageEncoder` | Protocol encoding/decoding | `encode()`, `decode()` |

---

## Migration Plan

### Phase 1: Core Infrastructure (No User Impact)

1. Create `voice_client/` package structure
2. Implement protocol layer (`protocol.py`, `exceptions.py`)
3. Implement `BaseClient` with connection management
4. Write unit tests for protocol and base client

### Phase 2: Audio Handling (No User Impact)

1. Implement `AudioHandler` for file I/O
2. Implement `AudioRecorder` and `AudioPlayer` for device I/O
3. Add audio validation and chunking
4. Write unit tests for audio components

### Phase 3: Client Implementation (No User Impact)

1. Implement `STTClient` with transcription methods
2. Implement `TTSClient` with synthesis methods
3. Implement `VoiceClient` for combined operations
4. Write integration tests with mock server

### Phase 4: Examples and Documentation (User-Facing)

1. Create example scripts demonstrating usage
2. Write README with installation and usage instructions
3. Document API reference
4. Test with real voice server

### Rollback Strategy

- Client is standalone - no server changes required
- Can be removed by deleting `voice_client/` directory
- No breaking changes to existing WebSocket API
- Users can continue using raw WebSocket if needed

---

## Open Questions

1. **Q:** Should we support reconnecting to a different server URL on failure?
   - **A:** No, keep it simple. Users can create a new client instance with different URL.

2. **Q:** Should we expose the underlying WebSocket connection for advanced users?
   - **A:** No, encapsulate completely. If advanced use cases emerge, add explicit API methods.

3. **Q:** Should we add logging/metrics for observability?
   - **A:** Add basic logging for errors and connection state changes. Full metrics can be added later if needed.

4. **Q:** Should we support multiple concurrent STT/TTS sessions per client?
   - **A:** No, one session per client instance. Users can create multiple client instances for parallel operations.

5. **Q:** Should we add a synchronous wrapper for users who don't want async?
   - **A:** No, async-only ensures consistency. Users can run async code in a thread if needed (document pattern).
