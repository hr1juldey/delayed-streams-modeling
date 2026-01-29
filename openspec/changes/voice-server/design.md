# Voice Server - Design Document

## Context

The voice server is a new FastAPI microservice that provides real-time Speech-to-Text (STT) and Text-to-Speech (TTS) capabilities via WebSocket connections. It will be consumed by an external DSPy + Ollama AI agent that orchestrates the conversation flow.

### Current State

- This is a new service being added to the `delayed-streams-modeling` repository
- Existing repo contains Kyutai STT scripts in `scripts/stt_from_file_pytorch.py` that will be extended
- Pocket TTS is an external package (`pocket-tts`) that will be integrated

### Constraints

- **GPU Memory**: RTX 3060 12GB VRAM shared with 2 LLMs, so STT model must fit in available space (~10GB free after LLMs)
- **Thread Safety**: Pocket TTS is NOT thread-safe, requires single-worker pattern
- **Latency Target**: <200ms for STT first token, real-time or better for TTS
- **Port**: 16000 range (avoiding port 8000 conflicts)
- **Python**: 3.10+ support required
- **Deployment**: Direct Python for development, Docker GPU for production (later phase)

### Stakeholders

- **DSPy Agent Developer**: Will consume STT/TTS WebSocket APIs
- **System Administrators**: Will deploy and monitor the service
- **End Users**: Expect low-latency, high-quality voice interaction

## Goals / Non-Goals

**Goals:**

- Provide production-ready WebSocket APIs for STT and TTS with low latency
- Support concurrent sessions with configurable limits
- Enable session management with history tracking and recovery
- Support custom voices with upload and management
- Provide monitoring via health/metrics endpoints
- Run efficiently on RTX 3060 (12GB) alongside 2 LLMs

**Non-Goals:**

- WebUI for testing (use example test clients instead)
- Built-in conversation orchestration (handled by external agent)
- STT model training/inference (using pre-trained Kyutai models)
- TTS model training (using pre-trained Pocket TTS)
- Global rate limiting (per-session only)

## Decisions

### Decision 1: Separate WebSocket Endpoints for STT and TTS

**Choice**: Use two separate WebSocket endpoints (`/api/v1/ws/stt` and `/api/v1/ws/tts`) rather than a single bidirectional endpoint.

**Rationale**:

- The external agent orchestrates the flow and needs separate control
- Simpler client implementation - agent can connect independently
- Easier to scale each service independently
- Clear separation of concerns

**Alternatives Considered**:

- **Single bidirectional WebSocket**: More complex, agent would need to multiplex
- **HTTP endpoints**: Not suitable for streaming audio

### Decision 2: Pocket TTS Single-Worker Pattern

**Choice**: Use a single TTS worker with asyncio queue to process requests serially.

**Rationale**:

- Pocket TTS is NOT thread-safe (documented constraint)
- Serial processing via asyncio.to_thread ensures thread safety
- Single worker queues requests and processes one at a time
- Trade-off: slightly higher latency for concurrent requests, but safe

**Alternatives Considered**:

- **Multiple workers**: Would violate thread-safety constraint
- **Process pool**: Overkill for CPU-only TTS, higher overhead

### Decision 3: MessagePack + JSON Dual Protocol Support

**Choice**: Support both MessagePack (default) and JSON encoding for WebSocket messages.

**Rationale**:

- MessagePack is more efficient for binary audio data
- JSON is more compatible for debugging and simple clients
- Content-type or config message determines format
- Best of both worlds

**Alternatives Considered**:

- **MessagePack only**: Less accessible for debugging
- **JSON only**: More overhead for binary audio data

### Decision 4: Session ID Server-Generated (UUID)

**Choice**: Server generates UUID session IDs rather than accepting client-provided IDs.

**Rationale**:

- Prevents session ID collisions
- Simplifies session management
- Ensures unique identifiers across the system
- Client can still "resume" by providing the server-generated ID on reconnect

**Alternatives Considered**:

- **Client-provided IDs**: Risk of collisions, more complex validation

### Decision 5: Pluggable Storage Backends

**Choice**: Support multiple storage backends (SQLite default, in-memory, extensible for others).

**Rationale**:

- SQLite is sufficient for most use cases
- In-memory for testing and development
- Extensible architecture allows future backends (PostgreSQL, Redis)
- Graceful degradation: if client provides history, use it; otherwise try to load from storage

**Alternatives Considered**:

- **SQLite only**: Less flexible for different deployment scenarios
- **PostgreSQL only**: Overkill for local deployment

### Decision 6: Pydantic Settings with ENV Nested Delimiter

**Choice**: Use Pydantic Settings with `__` nested delimiter for configuration (e.g., `VOICE_SERVER__STT__MODEL_NAME`).

**Rationale**:

- Type-safe configuration with validation
- Environment variable override support
- Nested structure mirrors the code organization
- 12-factor app compliant

**Alternatives Considered**:

- **TOML/YAML config files**: Less container-friendly
- **Simple ENV vars**: No nesting, harder to organize

### Decision 7: Configurable Audio Chunk Size

**Choice**: Make audio chunk size configurable rather than fixed.

**Rationale**:

- Different use cases require different chunk sizes (latency vs throughput)
- Default 1920 samples (80ms at 24kHz) for balanced performance
- Smaller chunks = lower latency, more overhead
- Larger chunks = higher latency, less overhead

**Alternatives Considered**:

- **Fixed chunk size**: Less flexible for different scenarios

### Decision 8: Graceful Model Switching

**Choice**: Implement graceful model switching with session draining for STT models.

**Rationale**:

- Allows runtime model switching without server restart
- Drain existing sessions before switching
- Prevents disruption to active users
- Important for GPU memory management (switch between 1B and 2.6B models)

**Alternatives Considered**:

- **Immediate switch**: Would disconnect active sessions
- **Restart required**: Downtime, poor user experience

## Risks / Trade-offs

### Risk 1: GPU Memory Exhaustion

**Risk**: Running STT model alongside 2 LLMs on 12GB GPU may cause OOM.

**Mitigation**:

- Use 1B-en_fr model by default (~2-3GB VRAM)
- Implement GPU memory monitoring
- Queue requests when GPU memory is full
- Provide clear documentation on memory requirements

### Risk 2: Pocket TTS Single Worker Bottleneck

**Risk**: Single TTS worker may become bottleneck under high concurrent load.

**Mitigation**:

- Document that TTS is CPU-only with serial processing
- Configure reasonable concurrent session limits
- Monitor queue depth and processing time
- Consider future optimization: multiple workers with voice-specific instances

### Risk 3: Session Storage Growth

**Risk**: Unlimited session history storage could exhaust disk space.

**Mitigation**:

- Implement max_history_length configuration
- Periodic cleanup of old sessions
- Provide session archive/export functionality
- Document storage requirements

### Risk 4: WebSocket Connection Leaks

**Risk**: Unclean client disconnects could leak connections and memory.

**Mitigation**:

- Implement heartbeat/ping to detect stale connections
- Timeout inactive sessions
- Proper cleanup in disconnect handlers
- Monitor active connection count

### Risk 5: Audio Backpressure Deadlock

**Risk**: Slow clients could cause server to block indefinitely.

**Mitigation**:

- Implement maximum buffer size with timeout
- Close connections that don't consume buffers
- Monitor buffer depth during processing
- Provide clear error messages to clients

## Migration Plan

### Phase 1: Foundation (Week 1-2)

1. Create project structure and configuration
2. Implement FastAPI app with health/metrics
3. Set up logging infrastructure
4. Create development environment scripts

### Phase 2: STT Integration (Week 3-4)

1. Extend Kyutai STT scripts for streaming
2. Implement STT WebSocket endpoint
3. Add session management basics
4. Create message protocol (JSON/MessagePack)
5. Build STT test client

### Phase 3: TTS Integration (Week 5-6)

1. Integrate Pocket TTS with thread-safe worker
2. Implement TTS WebSocket endpoint
3. Add voice management endpoints
4. Create TTS test client

### Phase 4: Advanced Features (Week 7-8)

1. Implement session recovery and history
2. Add runtime model switching
3. Implement voice upload and export
4. Add audio format conversions
5. Implement backpressure handling

### Phase 5: Production (Week 9-10)

1. Add API key authentication
2. Implement rate limiting
3. Add graceful shutdown
4. Create production Docker image
5. Write comprehensive documentation

### Rollback Strategy

- Git branches for each phase
- Ability to revert to previous working state
- Database migrations are versioned (if schema changes needed)
- Configuration changes are backward compatible where possible

## Open Questions

1. **STT Model Selection**: Should we auto-select model based on available VRAM, or require explicit configuration?
   - **Tentative**: Require explicit configuration for predictability

2. **Voice Cloning Quality**: What are the quality expectations for cloned voices vs pre-trained voices?
   - **Tentative**: Accept lower quality for custom voices, document expectations

3. **Session History Retention**: How long should session history be retained in storage?
   - **Tentative**: Configurable retention period, default 30 days

4. **Metrics Retention**: How long should metrics be retained before rollover?
   - **Tentative**: Use Prometheus default retention, not server concern

5. **Multi-Language Auto-Detection**: Should we support automatic language detection for the 1B-en_fr model?
   - **Tentative**: Yes, auto-detect and document in API
