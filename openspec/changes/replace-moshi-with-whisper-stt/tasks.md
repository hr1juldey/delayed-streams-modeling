# Replace Moshi with Faster-Whisper - Implementation Tasks

## 1. Dependencies and Configuration

- [x] 1.1 Update `voice_server/pyproject.toml` to replace moshi dependencies
  - Remove: `moshi==0.2.12`, `julius>=0.2.0`, `sphn>=0.1.0`
  - Remove: `openai-whisper>=20250625` (unused)
  - Add: `faster-whisper>=1.0.0`
- [x] 1.2 Update root `requirements.txt` to match pyproject.toml changes
- [x] 1.3 Update `voice_server/requirements.txt` to match pyproject.toml changes
- [x] 1.4 Update `voice_server/config/settings.py` STTSettings class
  - Change `model_name` Literal from `["1b-en_fr", "2.6b-en"]` to `["tiny", "base", "small", "medium", "large-v2", "large-v3"]`
  - Add `compute_type: Literal["default", "int8", "int16", "float16"] = "float16"`
  - Add `language: Optional[str] = None` for language selection
  - Change `warmup_on_startup` default from `False` to `True`
- [x] 1.5 Update `.env.example` with new STT configuration options

## 2. Base Classes and Types

- [x] 2.1 Update `voice_server/src/models/stt/base.py` STTModelName enum
  - Remove: `EN_FR_1B = "1b-en_fr"`, `EN_2_6B = "2.6b-en"`
  - Add: `TINY`, `BASE`, `SMALL`, `MEDIUM`, `LARGE_V2`, `LARGE_V3` enum values
- [x] 2.2 Update `voice_server/src/models/stt/base.py` STTConfig dataclass
  - Add `compute_type: str = "float16"` field
  - Add `language: Optional[str] = None` field
  - Remove `custom_vocabulary` field (not supported by Whisper)

## 3. Whisper STT Model Implementation

- [x] 3.1 Create `voice_server/src/models/stt/whisper.py` with imports and logger setup
  - Import: `asyncio`, `ThreadPoolExecutor`, `Optional`, `numpy`, `WhisperModel`
  - Use absolute imports only (CLAUDE_POLICY requirement)
- [x] 3.2 Implement `SessionState` dataclass in whisper.py
  - Fields: `audio_buffer: list[np.ndarray]`, `total_samples: int`
- [x] 3.3 Implement `WhisperSTTModel` class `__init__` method
  - Initialize config, model, executor, sessions, and flags
- [x] 3.4 Implement `_load_model` private method for executor thread
  - Create WhisperModel with device and compute_type
- [x] 3.5 Implement `initialize` async method
  - Create ThreadPoolExecutor with single worker
  - Load model via executor
  - Set _initialized flag
- [x] 3.6 Implement `start_stream` async method
  - Create new SessionState for session_id
  - Set _streaming_active flag
- [x] 3.7 Implement `process_audio_chunk` async method
  - Append audio to session's audio_buffer
  - Update total_samples count
  - Return None (no partial results for Whisper)
- [x] 3.8 Implement `_transcribe_sync` private method
  - Call model.transcribe with language, beam_size, vad_filter
  - Combine segments into full text
  - Return dict with text and avg_logprob
- [x] 3.9 Implement `finalize_stream` async method
  - Concatenate audio_buffer
  - Call _transcribe_sync via executor
  - Return STTResult with is_final=True
- [x] 3.10 Implement `end_stream` async method
  - Remove session from _sessions dict
  - Clear _streaming_active if no sessions remain
- [x] 3.11 Implement `_transcribe_with_timestamps_sync` private method
  - Call model.transcribe with word_timestamps=True
  - Build words list with timestamps
  - Return STTSegment
- [x] 3.12 Implement `transcribe` async method for non-streaming
  - Call _transcribe_with_timestamps_sync via executor
  - Return STTSegment
- [x] 3.13 Implement `switch_model` async method
  - Check for active sessions (raise if any)
  - Shutdown and reinitialize with new model
- [x] 3.14 Implement `get_model_info` method
  - Return dict with model info including model_type="whisper"
- [x] 3.15 Implement `shutdown` async method
  - Clear sessions, shutdown executor, clear model
- [x] 3.16 Add `__init__.py` export for WhisperSTTModel if needed (N/A)

## 4. Model Manager Integration

- [x] 4.1 Update `voice_server/src/models/stt/model_manager.py` imports
  - Remove: `from voice_server.src.models.stt.kyutai import KyutaiSTTModel`
  - Add: `from voice_server.src.models.stt.whisper import WhisperSTTModel`
- [x] 4.2 Update `STTModelManager.__init__` type hints
  - Change `_model: Optional[KyutaiSTTModel]` to `Optional[WhisperSTTModel]`
- [x] 4.3 Update `STTModelManager.initialize` method
  - Add `compute_type` to config creation (from settings)
  - Add `language` to config creation (from settings)
  - Change `KyutaiSTTModel(config)` to `WhisperSTTModel(config)`
- [x] 4.4 Update `STTModelManager.switch_model` references
  - Update any Kyutai-specific code to Whisper-agnostic

## 5. Deprecate Old Implementation

- [x] 5.1 Rename `voice_server/src/models/stt/kyutai.py` to `kyutai_deprecated.py`
  - Keep as backup for potential rollback
- [x] 5.2 Add deprecation notice comment at top of `kyutai_deprecated.py`
  - Explain why deprecated and what replaced it
- [x] 5.3 Update `voice_server/src/models/stt/__init__.py` if needed (N/A - empty file)
  - Remove KyutaiSTTModel exports
  - Add WhisperSTTModel exports

## 6. Testing and Verification

- [ ] 6.1 Create unit test for WhisperSTTModel initialization
  - Test model loading with different sizes
  - Test CPU and GPU device selection
  - Test different compute_type values
- [ ] 6.2 Create unit test for streaming transcription
  - Test start_stream, process_audio_chunk, finalize_stream flow
  - Verify audio accumulation works correctly
  - Test end_stream cleanup
- [ ] 6.3 Create unit test for non-streaming transcription
  - Test transcribe method with sample audio
  - Verify word timestamps are returned
- [ ] 6.4 Test CUDA 13.0 compatibility
  - Run server on CUDA 13.0 system
  - Verify no cuBLAS "Invalid handle" errors
  - Confirm transcription works correctly
- [ ] 6.5 Test STT WebSocket endpoint with audio files
  - Use `examples/stt_client.py` with `audio/bria.mp3`
  - Verify transcription returns correctly
  - Test with different model sizes
- [ ] 6.6 Verify audio resampling (24kHz → 16kHz)
  - Test that AudioProcessor correctly resamples for Whisper
  - Verify transcription accuracy with resampled audio
- [ ] 6.7 Test model warmup on startup
  - Verify warmup completes without errors
  - Check that first request after warmup is fast
- [ ] 6.8 Test language auto-detection
  - Test with multilingual audio if available
  - Verify correct language detection
- [ ] 6.9 Test explicit language selection
  - Set `language="en"` in settings
  - Verify transcription uses specified language
- [ ] 6.10 Test model switching
  - Start with base model, switch to small
  - Verify no active sessions requirement
  - Confirm switch succeeds

## 7. Documentation and Deployment

- [ ] 7.1 Update `README.md` with Whisper model information
  - Document available model sizes and memory requirements
  - Add note about CUDA 13.0 compatibility
  - Include model download size information
- [ ] 7.2 Update `.env.example` documentation
  - Document new STT configuration options
  - Add examples for different model sizes
  - Explain compute_type options
- [ ] 7.3 Update `voice_server/pyproject.toml` description
  - Update from "Kyutai STT" to "Whisper STT"
- [ ] 7.4 Create deployment script addition for model pre-download
  - Add to `scripts/start_prod.sh` or create new script
  - Pre-download configured model on first deployment
- [ ] 7.5 Update health endpoint documentation
  - Document new model_type="whisper" in health response
  - Update model information format
- [ ] 7.6 Update API documentation if needed
  - Note about streaming behavior (no partial results)
  - Clarify language auto-detection behavior

## 8. Code Quality and Compliance

- [ ] 8.1 Run `ruff check --fix` on all modified files
  - Fix any linting issues
- [ ] 8.2 Run `ruff format` on all modified files
  - Ensure consistent formatting
- [ ] 8.3 Verify absolute imports only (CLAUDE_POLICY requirement)
  - Check no relative imports in new code
  - Verify all imports use full module paths
- [ ] 8.4 Verify file size limits (CLAUDE_POLICY requirement)
  - Ensure whisper.py is under 100 lines of executable code
  - Split into multiple files if needed
- [ ] 8.5 Run type checking with mypy if configured
  - Fix any type errors in new code

## 9. Cleanup and Optimization

- [ ] 9.1 Remove any unused imports from modified files
- [ ] 9.2 Remove any commented-out code from modifications
- [ ] 9.3 Verify no debug print statements remain
- [ ] 9.4 Check for any hardcoded values that should be configurable
- [ ] 9.5 Verify logging is consistent and informative

## 10. Final Verification

- [ ] 10.1 Run full test suite (if exists)
- [ ] 10.2 Start server and verify no startup errors
- [ ] 10.3 Test complete STT flow: connect → send audio → receive transcription
- [ ] 10.4 Test TTS endpoint still works (verify no regression)
- [ ] 10.5 Test health endpoint returns correct model info
- [ ] 10.6 Verify metrics endpoint still works
- [ ] 10.7 Test concurrent sessions if applicable
- [ ] 10.8 Review git diff and verify all changes are intentional
