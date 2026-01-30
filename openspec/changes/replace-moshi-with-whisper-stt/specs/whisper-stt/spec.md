# Whisper STT Specification

## ADDED Requirements

### Requirement: Whisper model selection and loading
The system SHALL support loading Whisper STT models from the faster-whisper library, with support for multiple model sizes (tiny, base, small, medium, large-v2, large-v3).

#### Scenario: Load base Whisper model
- **WHEN** the server is configured with `model_name: "base"`
- **THEN** the system loads the Whisper base model using faster-whisper
- **AND** the model is initialized on the configured device (cuda or cpu)
- **AND** the system is ready to accept transcription requests

#### Scenario: Load tiny Whisper model for low resource usage
- **WHEN** the server is configured with `model_name: "tiny"`
- **THEN** the system loads the Whisper tiny model (~40MB)
- **AND** the model uses minimal GPU memory
- **AND** transcription speed is optimized with slight accuracy trade-off

#### Scenario: Load large-v3 model for maximum accuracy
- **WHEN** the server is configured with `model_name: "large-v3"`
- **THEN** the system loads the Whisper large-v3 model (~3GB)
- **AND** the system requires sufficient GPU memory (at least 6GB VRAM recommended)
- **AND** transcription accuracy is maximized

### Requirement: CUDA 13.0 compatibility
The system SHALL use faster-whisper (CTranslate2) which is compatible with CUDA 13.0, resolving the cuBLAS compatibility issues present in moshi.

#### Scenario: Successful model loading on CUDA 13.0
- **WHEN** the system initializes on CUDA 13.0
- **THEN** the Whisper model loads without "Invalid handle" errors
- **AND** cuBLAS library initializes successfully
- **AND** audio transcription processes correctly

#### Scenario: Fallback to CPU when CUDA unavailable
- **WHEN** the system is configured with `device: "cpu"`
- **THEN** the Whisper model loads in CPU-only mode
- **AND** transcription functions without GPU acceleration
- **AND** processing speed is slower but functional

### Requirement: Multi-language transcription support
The system SHALL support automatic language detection and explicit language selection for Whisper transcription.

#### Scenario: Automatic language detection
- **WHEN** `language` is set to `None` (default)
- **THEN** the system auto-detects the spoken language from audio
- **AND** transcribes the audio in the detected language
- **AND** returns the detected language code in the result metadata

#### Scenario: Explicit language selection
- **WHEN** `language` is set to a specific language code (e.g., "en", "fr", "es")
- **THEN** the system transcribes audio using only the specified language
- **AND** transcription accuracy is improved for the selected language

### Requirement: Compute type configuration
The system SHALL support multiple compute types for optimized performance across different hardware configurations.

#### Scenario: Float16 compute for GPU acceleration
- **WHEN** `compute_type` is set to "float16"
- **THEN** the system uses half-precision floating point for inference
- **AND** GPU memory usage is reduced
- **AND** inference speed is improved with minimal accuracy loss

#### Scenario: Int8 compute for maximum efficiency
- **WHEN** `compute_type` is set to "int8"
- **THEN** the system uses 8-bit integer quantization
- **AND** memory usage is minimized
- **AND** inference speed is maximized with some accuracy trade-off

### Requirement: VAD filtering integration
The system SHALL integrate Voice Activity Detection (VAD) filtering through faster-whisper's built-in VAD capabilities.

#### Scenario: VAD filtering enabled
- **WHEN** `vad_filter` is enabled in transcription parameters
- **THEN** the system automatically detects speech segments
- **AND** silence/non-speech audio is filtered out
- **AND** transcription results contain only spoken content

#### Scenario: VAD filtering disabled for client-side control
- **WHEN** `vad_filter` is disabled
- **THEN** the system processes all audio content including silence
- **AND** the client is responsible for speech segment detection

### Requirement: Word-level timestamps
The system SHALL provide word-level timestamps for transcribed audio when requested.

#### Scenario: Transcribe with word timestamps
- **WHEN** `word_timestamps` is enabled
- **THEN** the system returns each transcribed word with start and end times
- **AND** timestamps are in seconds relative to audio start
- **AND** results enable precise audio-to-text alignment

#### Scenario: Transcribe without word timestamps
- **WHEN** `word_timestamps` is disabled
- **THEN** the system returns only the full text transcription
- **AND** processing speed is improved by skipping timestamp computation

### Requirement: Streaming audio accumulation
The system SHALL accumulate audio chunks during streaming sessions and process the complete audio when the stream is finalized.

#### Scenario: Process accumulated audio chunks
- **WHEN** multiple audio chunks are received in a streaming session
- **THEN** the system accumulates chunks in a buffer
- **AND** processes the complete audio when finalize_stream is called
- **AND** returns a single final transcription result

#### Scenario: Handle empty audio stream
- **WHEN** a streaming session ends with no audio data
- **THEN** the system returns an empty transcription result
- **AND** no error is raised

### Requirement: Model switching at runtime
The system SHALL support switching between different Whisper model sizes without server restart, provided no active sessions exist.

#### Scenario: Switch from base to small model
- **WHEN** a model switch is requested from "base" to "small"
- **AND** no active streaming sessions exist
- **THEN** the system unloads the current model
- **AND** loads the new model
- **AND** resumes accepting new transcription requests

#### Scenario: Reject model switch with active sessions
- **WHEN** a model switch is requested
- **AND** active streaming sessions exist
- **THEN** the system rejects the switch request
- **AND** returns an error indicating active sessions must complete first

### Requirement: Beam search configuration
The system SHALL support configurable beam search size for transcription accuracy tuning.

#### Scenario: Use default beam size
- **WHEN** `beam_size` is not explicitly configured
- **THEN** the system uses beam_size=5 for balanced speed and accuracy

#### Scenario: Use larger beam size for accuracy
- **WHEN** `beam_size` is set to a higher value (e.g., 10)
- **THEN** the system uses the specified beam size
- **AND** transcription accuracy is improved
- **AND** processing time is increased

### Requirement: Language probability confidence
The system SHALL provide language probability as a confidence score for auto-detected languages.

#### Scenario: Return language probability
- **WHEN** language auto-detection is performed
- **THEN** the system returns a language_probability score (0.0 to 1.0)
- **AND** higher values indicate greater confidence in language detection
- **AND** the score is included in the transcription result metadata
