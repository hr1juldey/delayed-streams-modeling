# TTS WebSocket Specification

## ADDED Requirements

### Requirement: WebSocket connection for text-to-speech streaming
The system SHALL provide a WebSocket endpoint at `/api/v1/ws/tts` that accepts text input and returns audio output in real-time.

#### Scenario: Successful TTS WebSocket connection
- **WHEN** a client establishes a WebSocket connection to `/api/v1/ws/tts` with a valid API key
- **THEN** the server accepts the connection
- **AND** the server generates a unique session ID (UUID format)
- **AND** the server sends the session ID to the client

### Requirement: Text message format for TTS input
The system SHALL accept text messages in JSON or MessagePack format with `type: "Text"`, `data` containing the text to synthesize, and `session_id`.

#### Scenario: Receive complete text message
- **WHEN** the client sends a Text message with complete text
- **THEN** the server synthesizes the entire text to audio
- **AND** the server streams audio chunks back to the client

#### Scenario: Receive streaming text chunks
- **WHEN** the client sends multiple Text messages with partial text chunks
- **THEN** the server synthesizes each chunk as it arrives
- **AND** the server streams audio chunks continuously

### Requirement: Audio output formats
The system SHALL support multiple audio output formats: 24kHz int16 PCM, 24kHz float32 PCM, and WAV chunks with headers.

#### Scenario: Request int16 PCM output
- **WHEN** the client configures output format as "pcm_int16"
- **THEN** the server sends audio as 24kHz int16 PCM bytes
- **AND** the audio is directly playable by clients

#### Scenario: Request float32 PCM output
- **WHEN** the client configures output format as "pcm_float32"
- **THEN** the server sends audio as 24kHz float32 PCM bytes
- **AND** the audio maintains full precision

#### Scenario: Request WAV chunk output
- **WHEN** the client configures output format as "wav"
- **THEN** the server sends audio as WAV format chunks with headers
- **AND** each chunk is independently playable

### Requirement: Pocket TTS integration
The system SHALL use Pocket TTS (100M parameter model) running on CPU for text-to-speech synthesis.

#### Scenario: CPU-only TTS processing
- **WHEN** the server receives a text synthesis request
- **THEN** the server processes the request using CPU (not GPU)
- **AND** the server achieves approximately 6x faster than real-time synthesis

### Requirement: Thread-safe TTS processing
The system SHALL process TTS requests serially through a single worker to ensure thread safety, as Pocket TTS is not thread-safe.

#### Scenario: Multiple concurrent TTS requests
- **WHEN** multiple clients send TTS requests simultaneously
- **THEN** the server queues requests in a single worker
- **AND** the server processes requests serially
- **AND** the server maintains thread safety

### Requirement: Voice parameter controls
The system SHALL support adjustable voice parameters: speed, stability (CFG coefficient), and pitch.

#### Scenario: Adjust speaking speed
- **WHEN** the client sets `speed: 1.5`
- **THEN** the server synthesizes audio 1.5x faster than normal

#### Scenario: Adjust voice stability
- **WHEN** the client sets `stability: 2.0`
- **THEN** the server increases the CFG coefficient for more consistent voice output

#### Scenario: Adjust pitch
- **WHEN** the client sets `pitch: 1.2`
- **THEN** the server synthesizes audio with higher pitch

### Requirement: Audio normalization
The system SHALL normalize audio output levels for consistent volume across synthesis requests.

#### Scenario: Normalize audio output
- **WHEN** `enable_normalization` is true
- **THEN** the server normalizes audio levels before sending to client
- **AND** the output volume is consistent across different text inputs

### Requirement: End-of-stream marker
The system SHALL send an EOS (End of Stream) message when audio synthesis is complete.

#### Scenario: Send EOS after complete synthesis
- **WHEN** the server finishes synthesizing all text
- **THEN** the server sends a message with `type: "Eos"`
- **AND** the client knows synthesis is complete

### Requirement: Voice selection
The system SHALL support voice selection with a default voice and runtime voice switching capability.

#### Scenario: Use default voice
- **WHEN** the client connects without specifying a voice
- **THEN** the server uses the globally configured default voice
- **AND** the server synthesizes audio with the default voice

#### Scenario: Request specific voice
- **WHEN** the client specifies a voice_id in the config
- **THEN** the server loads the requested voice if available
- **AND** the server synthesizes audio with the requested voice

#### Scenario: Voice not found
- **WHEN** the client requests a voice_id that doesn't exist
- **THEN** the server sends an error message
- **AND** the server continues using the current voice
