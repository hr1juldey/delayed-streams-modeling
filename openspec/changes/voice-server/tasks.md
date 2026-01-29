# Voice Server - Implementation Tasks

## 1. Project Structure and Configuration

- [ ] 1.1 Create `voice-server/` directory structure with all subdirectories (config/, src/, tests/, examples/, data/, scripts/)
- [ ] 1.2 Create `pyproject.toml` with all dependencies (fastapi, uvicorn, websockets, pydantic, msgpack, pocket-tts, moshi, torch, julius, sphn, prometheus-client, aiosqlite)
- [ ] 1.3 Create `config/settings.py` with Pydantic Settings hierarchy (AudioSettings, STTSettings, TTSSettings, SessionSettings, ServerSettings)
- [ ] 1.4 Create `config/logging_config.py` for structured JSON logging to stdout and detailed file logging with rotation
- [ ] 1.5 Create `.env.example` with all configurable environment variables documented
- [ ] 1.6 Create `README.md` with project overview, setup instructions, and usage examples

## 2. Core FastAPI Application

- [ ] 2.1 Create `src/main.py` FastAPI application entry point with CORS middleware configuration
- [ ] 2.2 Create `src/core/lifecycle.py` with startup/shutdown handlers for model loading and cleanup
- [ ] 2.3 Create `src/core/exceptions.py` with custom exception classes for voice server errors
- [ ] 2.4 Create `src/core/security.py` with API key authentication dependency
- [ ] 2.5 Create `src/api/dependencies.py` with FastAPI dependencies for auth and session management
- [ ] 2.6 Create `src/api/middleware.py` with rate limiting middleware (per-session limits)

## 3. WebSocket Protocol

- [ ] 3.1 Create `src/services/websocket/protocol.py` with MessageProtocol class supporting JSON and MessagePack encoding/decoding
- [ ] 3.2 Create `src/services/websocket/connection.py` with ConnectionManager for managing active WebSocket connections
- [ ] 3.3 Create `src/services/websocket/heartbeat.py` with ping/pong heartbeat management
- [ ] 3.4 Define message types (MessageType enum: Audio, Text, Error, EOS, Config) and Message dataclass
- [ ] 3.5 Implement message encoding/decoding for both JSON and MessagePack formats
- [ ] 3.6 Implement session ID routing in ConnectionManager

## 4. Audio Processing

- [ ] 4.1 Create `src/utils/audio.py` with audio resampling utilities using julius
- [ ] 4.2 Create `src/services/audio/processor.py` with AudioProcessor for format conversion (float32/int16/WAV)
- [ ] 4.3 Create `src/services/audio/buffer.py` with AudioBuffer implementing backpressure handling
- [ ] 4.4 Create `src/services/audio/vad.py` with VoiceActivityDetection wrapper for server-side VAD
- [ ] 4.5 Implement audio normalization for TTS output
- [ ] 4.6 Implement WAV chunk generation with proper headers

## 5. STT Model Integration

- [ ] 5.1 Create `src/models/stt/base.py` with STTModelBase abstract interface (initialize, process_audio_chunk, finalize_stream, switch_model)
- [ ] 5.2 Create `src/models/stt/kyutai.py` with KyutaiSTTModel extending `scripts/stt_from_file_pytorch.py` patterns
- [ ] 5.3 Implement CheckpointInfo.from_hf_repo() integration for model loading
- [ ] 5.4 Implement Mimi encoder integration for audio tokenization
- [ ] 5.5 Implement LMGen streaming with step_with_extra_heads() for VAD
- [ ] 5.6 Implement custom vocabulary support via prompting
- [ ] 5.7 Create `src/models/stt/model_manager.py` with STTModelManager for model loading and graceful switching
- [ ] 5.8 Implement model warmup on startup
- [ ] 5.9 Implement runtime model switching with session draining

## 6. STT WebSocket Endpoint

- [ ] 6.1 Create `src/api/routes/websocket_stt.py` with `/api/v1/ws/stt` WebSocket endpoint
- [ ] 6.2 Implement authentication via API key header
- [ ] 6.3 Implement session generation (UUID) and session state initialization
- [ ] 6.4 Implement config message handling (streaming mode, VAD mode, audio format)
- [ ] 6.5 Implement audio message receiving loop with buffer management
- [ ] 6.6 Implement STT processing through KyutaiSTTModel
- [ ] 6.7 Implement text result sending with partial/final/is_final markers
- [ ] 6.8 Implement EOS handling and final result delivery
- [ ] 6.9 Implement error handling and connection cleanup

## 7. TTS Model Integration

- [ ] 7.1 Create `src/models/tts/base.py` with TTSModelBase abstract interface (initialize, synthesize_stream, synthesize)
- [ ] 7.2 Create `src/models/tts/pocket.py` with PocketTTSModel using external pocket-tts package
- [ ] 7.3 Create `src/models/tts/worker.py` with TTSWorker for thread-safe serial processing
- [ ] 7.4 Implement asyncio.to_thread wrapper for CPU-bound TTS generation
- [ ] 7.5 Implement request queue for concurrent session handling
- [ ] 7.6 Create `src/models/tts/model_manager.py` with TTSModelManager for voice loading and management
- [ ] 7.7 Implement voice parameter controls (speed, stability/CFG, pitch)

## 8. TTS WebSocket Endpoint

- [ ] 8.1 Create `src/api/routes/websocket_tts.py` with `/api/v1/ws/tts` WebSocket endpoint
- [ ] 8.2 Implement authentication via API key header
- [ ] 8.3 Implement session generation and state initialization
- [ ] 8.4 Implement config message handling (voice selection, output format, voice parameters)
- [ ] 8.5 Implement text message receiving loop (support both streaming and complete modes)
- [ ] 8.6 Implement TTS processing through PocketTTSModel and TTSWorker
- [ ] 8.7 Implement audio chunk streaming in requested format (int16/float32/WAV)
- [ ] 8.8 Implement EOS marker sending after synthesis complete
- [ ] 8.9 Implement error handling and connection cleanup

## 9. Session Management

- [ ] 9.1 Create `src/services/session/models.py` with SessionHistory, ConversationTurn, and SessionState dataclasses
- [ ] 9.2 Create `src/db/base.py` with database connection handling
- [ ] 9.3 Create `src/db/repositories.py` with session and voice repositories
- [ ] 9.4 Create `src/services/session/store.py` with SessionStoreBase abstract interface
- [ ] 9.5 Create SQLiteSessionStore implementation in `src/services/session/store.py`
- [ ] 9.6 Create InMemorySessionStore implementation for testing
- [ ] 9.7 Create `src/services/session/manager.py` with SessionManager for session lifecycle
- [ ] 9.8 Implement create_or_resume_session with client-provided history support
- [ ] 9.9 Implement session activity tracking and timeout handling
- [ ] 9.10 Implement concurrent session limits with semaphore
- [ ] 9.11 Implement background cleanup task for expired sessions

## 10. Voice Management

- [ ] 10.1 Create `src/api/routes/voice.py` with voice management HTTP endpoints
- [ ] 10.2 Implement POST `/api/v1/voice/upload` for audio file upload with Pocket TTS export to .safetensors
- [ ] 10.3 Implement GET `/api/v1/voice/list` for listing available voices
- [ ] 10.4 Implement POST `/api/v1/voice/switch` for switching active voice
- [ ] 10.5 Implement DELETE `/api/v1/voice/{voice_id}` for voice deletion
- [ ] 10.6 Implement GET `/api/v1/voice/{voice_id}` for voice metadata
- [ ] 10.7 Implement voice storage in configured voices_path directory
- [ ] 10.8 Implement voice file validation and error handling

## 11. Health and Metrics

- [ ] 11.1 Create `src/api/routes/health.py` with `/health` and `/metrics` endpoints
- [ ] 11.2 Implement `/health` endpoint returning status and model information
- [ ] 11.3 Create `src/utils/metrics.py` with Prometheus metrics definitions
- [ ] 11.4 Implement active_sessions gauge metric
- [ ] 11.5 Implement stt_request_latency_ms and tts_request_latency_ms histogram metrics
- [ ] 11.6 Implement model_status gauge metric with labels
- [ ] 11.7 Implement error_total counter metric with error type labels
- [ ] 11.8 Implement websocket_connections_total counter metric
- [ ] 11.9 Implement audio_processing_bytes_total counter metric
- [ ] 11.10 Implement gpu_memory_bytes gauge metric (when GPU available)
- [ ] 11.11 Implement session_timeouts_total counter metric
- [ ] 11.12 Implement `/metrics` endpoint returning Prometheus format

## 12. Testing and Examples

- [ ] 12.1 Create `examples/stt_client.py` test client for STT WebSocket
- [ ] 12.2 Create `examples/tts_client.py` test client for TTS WebSocket
- [ ] 12.3 Create `examples/full_conversation.py` demonstrating complete STT + TTS flow
- [ ] 12.4 Test STT WebSocket connection with API key authentication
- [ ] 12.5 Test STT audio streaming with partial and final results
- [ ] 12.6 Test STT model switching (1B ↔ 2.6B)
- [ ] 12.7 Test TTS WebSocket connection with text input
- [ ] 12.8 Test TTS streaming text chunks vs complete text
- [ ] 12.9 Test TTS output formats (int16, float32, WAV)
- [ ] 12.10 Test voice upload, listing, switching, and deletion
- [ ] 12.11 Test session recovery with same session_id
- [ ] 12.12 Test concurrent STT sessions
- [ ] 12.13 Test concurrent TTS sessions (thread-safe)
- [ ] 12.14 Test session timeout and cleanup

## 13. Production Readiness

- [ ] 13.1 Implement graceful shutdown with connection draining
- [ ] 13.2 Add API key authentication with configurable key list
- [ ] 13.3 Implement rate limiting per session
- [ ] 13.4 Create production Dockerfile with GPU support
- [ ] 13.5 Create `docker-compose.yml` for development environment
- [ ] 13.6 Create `scripts/start_dev.sh` development startup script
- [ ] 13.7 Create `scripts/start_prod.sh` production startup script
- [ ] 13.8 Update README with deployment instructions
- [ ] 13.9 Document environment variables and configuration options
- [ ] 13.10 Document API endpoints and message formats
