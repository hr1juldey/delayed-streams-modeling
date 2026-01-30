# Replace Moshi with Faster-Whisper - Design Document

## Context

### Current State

The voice server currently uses Kyutai's moshi STT library (v0.2.12) for speech-to-text transcription. The implementation includes:
- `KyutaiSTTModel` class in `voice_server/src/models/stt/kyutai.py`
- Model sizes: 1B-en_fr (bilingual) and 2.6B-en (English only)
- Models loaded from HuggingFace: `kyutai/stt-{model_name}-candle`
- ThreadPoolExecutor for CUDA context management
- Streaming architecture with Mimi encoder + LMGen

### Problem

Moshi has a CUDA version compatibility issue:
- PyTorch 2.9.1+cu128 is built with CUDA 12.8
- System has CUDA 13.0 installed
- Moshi's cuBLAS library expects CUDA 12.8, causing "Invalid handle" errors
- This makes the STT WebSocket endpoint non-functional

### Constraints

- **GPU Memory**: RTX 3060 12GB VRAM shared with 2 LLMs
- **API Compatibility**: WebSocket endpoint must remain unchanged for existing clients
- **Deployment**: Direct Python for development, must support both CUDA and CPU
- **CLAUDE_POLICY**: Absolute imports only, Ruff compliance, file size limits

### Stakeholders

- **DSPy Agent Developer**: Consumes STT WebSocket API, expects stable interface
- **System Administrators**: Deploy and monitor the service
- **End Users**: Expect working voice transcription

## Goals / Non-Goals

**Goals:**
- Replace moshi with faster-whisper for CUDA 13.0 compatibility
- Maintain existing WebSocket API contract (no breaking changes for clients)
- Support multiple Whisper model sizes with different memory/speed trade-offs
- Maintain session management and streaming architecture
- Enable model warmup on startup (currently disabled due to moshi issues)

**Non-Goals:**
- Implementing true streaming transcription (Whisper processes complete utterances)
- Changing WebSocket message protocol or formats
- Modifying TTS functionality
- Adding new WebSocket endpoints

## Decisions

### Decision 1: Use faster-whisper (not openai-whisper)

**Choice**: Use `faster-whisper` package instead of `openai-whisper`.

**Rationale:**
- faster-whisper uses CTranslate2 for better CUDA version compatibility
- 4x faster inference than openai-whisper with same accuracy
- Lower memory footprint due to CTranslate2 optimization
- Active maintenance and production-ready
- Built-in VAD filtering via `vad_filter` parameter

**Alternatives Considered:**
- **openai-whisper**: Slower, higher memory, no streaming advantage
- **whisper_streaming (ufal)**: Additional wrapper layer, less control
- **whisper-live**: More complex, focuses on real-time use cases we don't need

### Decision 2: Create New WhisperSTTModel Class

**Choice**: Create new `WhisperSTTModel` class implementing `STTModelBase` interface, keeping existing architecture.

**Rationale:**
- Maintains clean separation between model implementations
- Preserves existing session management, WebSocket handling, and audio processing
- Allows potential future model additions (e.g., keeping moshi as fallback)
- Follows existing patterns in the codebase

**Alternatives Considered:**
- **Modify KyutaiSTTModel in place**: Would lose history, harder to revert
- **Create entirely new architecture**: Unnecessary complexity, breaks existing patterns

### Decision 3: Audio Accumulation Strategy for Streaming

**Choice**: Accumulate audio chunks in session state, process complete audio at `finalize_stream()`.

**Rationale:**
- Whisper does not support true streaming (processes complete utterances)
- Simpler implementation than attempting chunk-based processing
- Matches client behavior where client controls speech segment boundaries (VAD)
- Maintains API compatibility - clients still send chunks, get results at end

**Alternatives Considered:**
- **Chunk-based processing with sliding window**: More complex, Whisper not designed for it
- **Real-time incremental transcription**: Would require different STT engine

### Decision 4: Model Size Options

**Choice**: Support standard Whisper model sizes: tiny, base, small, medium, large-v2, large-v3.

**Rationale:**
- Covers range from minimal resource usage (tiny ~40MB) to maximum accuracy (large-v3 ~3GB)
- Standard naming from faster-whisper, clear semantics
- Allows users to optimize for their hardware constraints
- Default to "base" for balance (~140MB, good accuracy)

**Alternatives Considered:**
- **Support only single model**: Less flexibility for different deployments
- **Support quantized variants only**: More complex, less standard

### Decision 5: ThreadPoolExecutor for CUDA Context

**Choice**: Continue using ThreadPoolExecutor pattern with single worker thread.

**Rationale:**
- Maintains CUDA context consistency (PyTorch CUDA contexts are thread-local)
- Proven pattern from existing implementation
- Serial processing acceptable for STT workload
- Cleaner than alternative approaches

**Alternatives Considered:**
- **Process pool**: Higher overhead, more complex
- **Multiple workers**: Risk of CUDA context issues

### Decision 6: Compute Type Configuration

**Choice**: Support multiple compute types: default, int8, int16, float16.

**Rationale:**
- Allows performance tuning for different hardware
- float16 provides good balance of speed and accuracy
- int8 maximizes efficiency for edge deployments
- Default to float16 for GPU acceleration

**Alternatives Considered:**
- **Fixed compute type**: Less flexibility
- **Runtime auto-selection**: More complex, unpredictable behavior

## Risks / Trade-offs

### Risk 1: True Streaming Not Supported

**Risk**: Clients expecting real-time partial results during speech will only get results at utterance end.

**Mitigation**:
- Document clearly that Whisper processes complete utterances
- Existing streaming_mode "partial" will have limited utility
- Consider adding note in API documentation about latency characteristics
- Future work: explore incremental Whisper implementations if needed

### Risk 2: Model Download on First Use

**Risk**: First model download may be slow (base model ~140MB, large-v3 ~3GB).

**Mitigation**:
- Document model download requirement
- Consider pre-downloading models in deployment scripts
- Add progress logging during model loading
- Cache models in standard HF cache location

### Risk 3: Memory Footprint Variation

**Risk**: Larger models may exceed available GPU memory when running alongside LLMs.

**Mitigation**:
- Default to "base" model (~140MB VRAM)
- Document memory requirements for each model size
- Monitor GPU memory usage in health endpoint
- Provide clear guidance on model selection for resource-constrained deployments

### Risk 4: Language Detection Overhead

**Risk**: Auto language detection adds processing time and may be less accurate for short utterances.

**Mitigation**:
- Allow explicit language selection via configuration
- Document trade-offs between auto-detection and explicit selection
- Use auto-detection as default for flexibility

### Risk 5: Audio Sample Rate Assumptions

**Risk**: Implementation assumes 16kHz audio (Whisper's native rate), but current system uses 24kHz.

**Mitigation**:
- AudioProcessor already handles resampling
- Verify resampling works correctly (24kHz → 16kHz for Whisper)
- Document sample rate requirements

## Migration Plan

### Phase 1: Dependencies and Configuration (Week 1)

1. Update `pyproject.toml`:
   - Remove: `moshi==0.2.12`, `julius>=0.2.0`, `sphn>=0.1.0`
   - Add: `faster-whisper>=1.0.0`

2. Update `voice_server/config/settings.py`:
   - Change `model_name` Literal to Whisper model sizes
   - Add `compute_type` parameter
   - Add `language` parameter
   - Re-enable `warmup_on_startup` default to `True`

### Phase 2: Implementation (Week 2)

1. Create `voice_server/src/models/stt/whisper.py`
2. Update `voice_server/src/models/stt/base.py`:
   - Update `STTModelName` enum
   - Add `compute_type` to `STTConfig`
3. Update `voice_server/src/models/stt/model_manager.py`:
   - Import `WhisperSTTModel`
   - Update model instantiation

### Phase 3: Testing (Week 3)

1. Unit tests for WhisperSTTModel
2. Integration tests for STT WebSocket endpoint
3. Test with various model sizes
4. Verify CUDA 13.0 compatibility
5. Test audio resampling (24kHz → 16kHz)

### Phase 4: Deployment (Week 4)

1. Update deployment documentation
2. Add model pre-download to deployment scripts
3. Monitor for issues in production
4. Update example clients if needed

### Rollback Strategy

- Keep `kyutai.py` file as reference/backup (rename to `kyutai_deprecated.py`)
- Git commit before migration for easy revert
- Can revert dependency changes and use old implementation if critical issues arise
- API contract unchanged means client-side changes not required

## Open Questions

1. **Sample Rate Handling**: Should we resample in WhisperSTTModel or rely on AudioProcessor?
   - **Tentative**: Let AudioProcessor handle resampling (24kHz → 16kHz)

2. **Partial Results**: How should we handle streaming_mode="partial" with Whisper?
   - **Tentative**: Return no partial results, only final at end of stream. Document this limitation.

3. **Model Caching**: Should we pre-download models during deployment?
   - **Tentative**: Yes, add to deployment scripts for production environments.

4. **Confidence Scores**: How to map Whisper's language_probability to our confidence threshold?
   - **Tentative**: Use language_probability directly as confidence score (0.0 to 1.0 range matches).

5. **Error Handling**: How should we handle model download failures?
   - **Tentative**: Raise ModelException with clear message, include retry logic in model manager.
