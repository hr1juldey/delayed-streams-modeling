# Replace Moshi STT with Faster-Whisper - Proposal

## Why

The Kyutai moshi STT library (v0.2.12) has CUDA 13.0 compatibility issues causing "Invalid handle" cuBLAS errors during audio processing. The library was built for CUDA 12.8 but fails on systems running CUDA 13.0, which is our current environment. This makes the STT WebSocket endpoint non-functional. We need to replace moshi with a more CUDA-compatible STT solution to restore voice server functionality.

## What Changes

- **BREAKING**: Replace `moshi==0.2.12` dependency with `faster-whisper>=1.0.0`
- Remove dependencies: `julius>=0.2.0`, `sphn>=0.1.0` (moshi-specific)
- **BREAKING**: Replace STT model options from Kyutai models (`1b-en_fr`, `2.6b-en`) to Whisper models (`tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3`)
- Create new `WhisperSTTModel` class implementing `STTModelBase` interface
- Update `STTSettings` configuration to support Whisper-specific parameters (`compute_type`, `language`)
- Remove or deprecate `voice_server/src/models/stt/kyutai.py` (can keep as optional backup)
- Update `STTModelManager` to use `WhisperSTTModel` instead of `KyutaiSTTModel`

## Capabilities

### New Capabilities
- `whisper-stt`: Whisper-based speech-to-text transcription using faster-whisper (CTranslate2) with support for multiple model sizes, multilingual transcription, and CUDA 13.0 compatibility

### Modified Capabilities
- `stt-websocket`: Underlying implementation changes from moshi to faster-whisper, but API contract remains the same. No spec-level requirement changes - clients continue using the same WebSocket endpoint with identical message formats.

## Impact

### Affected Code
- `voice_server/src/models/stt/whisper.py` - NEW FILE
- `voice_server/src/models/stt/base.py` - Update `STTModelName` enum, add `compute_type` to `STTConfig`
- `voice_server/src/models/stt/model_manager.py` - Import and use `WhisperSTTModel`
- `voice_server/config/settings.py` - Update `STTSettings` with Whisper parameters
- `voice_server/src/models/stt/kyutai.py` - DEPRECATED (may be removed)

### Dependencies
- Remove: `moshi==0.2.12`, `julius>=0.2.0`, `sphn>=0.1.0`
- Add: `faster-whisper>=1.0.0`

### API Impact
- **No breaking changes** to WebSocket API (`/api/v1/ws/stt`)
- Message protocol unchanged (Audio/Text/EOS messages)
- Session management unchanged
- Configuration changes only: model names and new optional parameters

### System Impact
- Resolves CUDA 13.0 compatibility issues
- May have different latency characteristics (Whisper processes complete utterances, not true streaming)
- Model download on first use (Whisper models from HuggingFace)
- Memory footprint varies by model size (tiny ~40MB, base ~140MB, small ~460MB, medium ~1.5GB, large-v3 ~3GB)
