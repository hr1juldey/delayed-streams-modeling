# Audio Processing Specification

## ADDED Requirements

### Requirement: Audio format conversion
The system SHALL convert between different audio formats (float32, int16, WAV) for input and output.

#### Scenario: Convert int16 to float32 for STT
- **WHEN** the STT input is configured for int16 format
- **THEN** the server converts int16 PCM to float32 PCM
- **AND** the server processes the converted audio through the STT model

#### Scenario: Convert float32 to int16 for TTS output
- **WHEN** the TTS output is configured for int16 format
- **THEN** the server converts float32 PCM to int16 PCM
- **AND** the server sends the converted audio to the client

### Requirement: Audio resampling
The system SHALL resample audio to match the required sample rate (24kHz) for processing.

#### Scenario: Upsample audio for processing
- **WHEN** input audio sample rate is lower than 24kHz (e.g., 16kHz)
- **THEN** the server resamples the audio to 24kHz
- **AND** the server maintains audio quality during resampling

#### Scenario: Downsample audio for processing
- **WHEN** input audio sample rate is higher than 24kHz (e.g., 48kHz)
- **THEN** the server resamples the audio to 24kHz
- **AND** the server uses appropriate anti-aliasing

### Requirement: Audio normalization
The system SHALL normalize audio levels to ensure consistent volume across audio inputs and outputs.

#### Scenario: Normalize input audio
- **WHEN** `enable_audio_normalization` is true for TTS
- **THEN** the server normalizes output audio levels
- **AND** the server applies peak normalization to prevent clipping

#### Scenario: Skip normalization when disabled
- **WHEN** `enable_audio_normalization` is false
- **THEN** the server outputs audio without normalization
- **AND** the audio maintains original levels

### Requirement: Audio chunk processing
The system SHALL process audio in configurable chunk sizes optimized for real-time streaming.

#### Scenario: Process with default chunk size
- **WHEN** no custom chunk_size is configured
- **THEN** the server uses the default chunk size (1920 samples = 80ms at 24kHz)

#### Scenario: Process with custom chunk size
- **WHEN** a custom chunk_size is configured
- **THEN** the server processes audio in the configured chunk size
- **AND** the server adjusts buffering accordingly

### Requirement: Audio backpressure handling
The system SHALL implement backpressure to prevent memory overload when clients are slow to consume audio.

#### Scenario: Apply backpressure on slow client
- **WHEN** the audio buffer is full (client not consuming fast enough)
- **THEN** the server blocks incoming audio processing
- **AND** the server waits for buffer space to become available
- **AND** the server does not drop audio data

#### Scenario: Resume processing when buffer clears
- **WHEN** the slow client resumes consuming audio
- **AND** buffer space becomes available
- **THEN** the server resumes processing incoming audio

### Requirement: WAV chunk generation
The system SHALL generate WAV format chunks with proper headers for clients that need self-contained audio chunks.

#### Scenario: Generate WAV chunks for TTS
- **WHEN** TTS output format is configured as "wav"
- **THEN** the server wraps each audio chunk in WAV format
- **AND** the server includes proper WAV headers (RIFF, fmt, data chunks)
- **AND** each chunk is independently playable

### Requirement: Audio buffer management
The system SHALL manage audio buffers with configurable maximum size to prevent memory exhaustion.

#### Scenario: Buffer reaches maximum size
- **WHEN** the audio buffer reaches its maximum configured size
- **THEN** the server stops accepting new audio data
- **AND** the server applies backpressure to the sender
- **AND** the server does not crash or exceed memory limits

### Requirement: Sample rate configuration
The system SHALL support configurable input and output sample rates with default of 24kHz.

#### Scenario: Use default 24kHz sample rate
- **WHEN** no custom sample rate is configured
- **THEN** the server processes audio at 24kHz
- **AND** all components use 24kHz as the standard

#### Scenario: Configure custom sample rate
- **WHEN** a custom sample rate is configured
- **THEN** the server processes audio at the configured rate
- **AND** the server adjusts resampling accordingly
