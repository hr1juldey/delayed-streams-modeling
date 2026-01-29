# STT WebSocket Specification

## ADDED Requirements

### Requirement: WebSocket connection for speech-to-text streaming
The system SHALL provide a WebSocket endpoint at `/api/v1/ws/stt` that accepts audio input and returns text transcription results in real-time.

#### Scenario: Successful STT WebSocket connection
- **WHEN** a client establishes a WebSocket connection to `/api/v1/ws/stt` with a valid API key
- **THEN** the server accepts the connection
- **AND** the server generates a unique session ID (UUID format)
- **AND** the server sends the session ID to the client

#### Scenario: Connection without API key when authentication is required
- **WHEN** a client connects without an API key and `require_auth` is true
- **THEN** the server rejects the connection with authentication error

### Requirement: Audio message format for STT input
The system SHALL accept audio messages in JSON or MessagePack format with `type: "Audio"`, `data` containing PCM audio samples, and `session_id`.

#### Scenario: Receive audio chunk in float32 format
- **WHEN** the client sends an Audio message with float32 PCM data
- **THEN** the server processes the audio chunk through the STT model
- **AND** the server returns transcription results

#### Scenario: Receive audio chunk in int16 format
- **WHEN** the client sends an Audio message with int16 PCM data
- **AND** the server is configured to accept int16 format
- **THEN** the server converts to float32 and processes through STT model

### Requirement: Streaming transcription modes
The system SHALL support three streaming modes: "partial" (stream partial results as detected), "final" (wait for complete utterance), and "both" (send both partial and final results).

#### Scenario: Partial streaming mode
- **WHEN** the client configures streaming_mode as "partial"
- **THEN** the server sends text results as they are detected during speech
- **AND** the results are marked as partial (not final)

#### Scenario: Final only streaming mode
- **WHEN** the client configures streaming_mode as "final"
- **THEN** the server waits until speech end is detected
- **AND** the server sends the complete final transcription

#### Scenario: Both streaming modes
- **WHEN** the client configures streaming_mode as "both"
- **THEN** the server sends partial results during speech
- **AND** the server sends a final result when speech ends
- **AND** final results are marked with `is_final: true`

### Requirement: Voice Activity Detection (VAD)
The system SHALL support both client-side and server-side VAD modes for detecting speech end.

#### Scenario: Client-side VAD mode
- **WHEN** the server is configured with `vad_mode: "client"`
- **THEN** the server relies on the client to send EOS markers
- **AND** the server processes audio until EOS is received

#### Scenario: Server-side VAD mode
- **WHEN** the server is configured with `vad_mode: "server"`
- **THEN** the server uses semantic VAD from the Kyutai STT model
- **AND** the server automatically detects speech end
- **AND** the server sends final transcription when silence is detected

### Requirement: Model selection and switching
The system SHALL support Kyutai STT models (1B-en_fr or 2.6b-en) with runtime model switching capability.

#### Scenario: Load 1B-en_fr model
- **WHEN** the server is configured with `model_name: "1b-en_fr"`
- **THEN** the server loads the 1B parameter English+French model
- **AND** the model operates with approximately 0.5s delay

#### Scenario: Load 2.6B-en model
- **WHEN** the server is configured with `model_name: "2.6b-en"`
- **THEN** the server loads the 2.6B parameter English-only model
- **AND** the model operates with approximately 2.5s delay

#### Scenario: Runtime model switch with graceful drain
- **WHEN** a runtime model switch is requested
- **THEN** the server stops accepting new sessions
- **AND** the server waits for existing sessions to complete
- **AND** the server unloads the current model
- **AND** the server loads the new model
- **AND** the server resumes accepting new sessions

### Requirement: Confidence scores
The system SHALL provide confidence scores for transcription results when enabled via configuration.

#### Scenario: Confidence scores enabled
- **WHEN** `confidence_threshold` is configured (e.g., 0.5)
- **THEN** the server includes confidence score with each text result
- **AND** results below the threshold are marked as low confidence

### Requirement: Custom vocabulary support
The system SHALL support custom vocabulary words to improve transcription accuracy for domain-specific terms.

#### Scenario: Custom vocabulary configured
- **WHEN** `custom_vocabulary` list is provided with domain terms
- **THEN** the server incorporates these terms into the STT model via prompting
- **AND** the server transcribes these terms with higher accuracy

### Requirement: Multi-language support
The system SHALL support configurable language selection for STT processing.

#### Scenario: English+French model
- **WHEN** using the "1b-en_fr" model
- **THEN** the server transcribes both English and French speech
- **AND** the server can auto-detect the language if configured

#### Scenario: English-only model
- **WHEN** using the "2.6b-en" model
- **THEN** the server transcribes English speech only
- **AND** the server provides higher accuracy for English content

### Requirement: Target latency
The system SHALL target sub-200ms latency from audio chunk receipt to first text result.

#### Scenario: Low latency processing
- **WHEN** the server is configured with `target_latency_ms: 200`
- **THEN** the server processes audio chunks within 200ms
- **AND** the server sends partial results within the target latency
