# TTS Client Specification

**Version:** 1.0

## ADDED Requirements

### Requirement: TTSClient initialization

The system SHALL provide a `TTSClient` class for Text-to-Speech synthesis via WebSocket.

#### Scenario: Creating client with default parameters

- **WHEN** creating a `TTSClient` with no parameters
- **THEN** the following defaults SHALL be used:
  - `url: "ws://localhost:16000/api/v1/ws/tts"`
  - `encoding: "json"`
  - `timeout: 30.0` seconds
  - `api_key: None`

#### Scenario: Creating client with custom parameters

- **WHEN** creating a `TTSClient(url="ws://example.com", encoding="msgpack", timeout=60.0)`
- **THEN** the client SHALL use the specified parameters

#### Scenario: Default configuration values

- **WHEN** a `TTSClient` is initialized
- **THEN** the following default config SHALL be set:
  - `voice_id: "default"`
  - `output_format: "pcm_int16"`
  - `streaming: True`

---

### Requirement: Async context manager support

The system SHALL support `async with` for automatic connection lifecycle management.

#### Scenario: Context manager connects on enter

- **GIVEN** a `TTSClient` instance
- **WHEN** entering the context manager with `async with TTSClient() as tts`
- **THEN** the system SHALL automatically connect to the WebSocket server
- **AND** a unique `session_id` SHALL be generated
- **AND** the client instance SHALL be returned

#### Scenario: Context manager disconnects on exit

- **GIVEN** an active `TTSClient` connection within a context manager
- **WHEN** exiting the context manager (normally or via exception)
- **THEN** the system SHALL gracefully close the WebSocket connection
- **AND** all resources SHALL be cleaned up

---

### Requirement: Configuration message sending

The system SHALL provide a `configure()` method for sending initial configuration to the server.

#### Scenario: Sending default configuration

- **GIVEN** a connected `TTSClient`
- **WHEN** calling `configure()`
- **THEN** a `ConfigMessage` SHALL be sent to the server
- **AND** the message SHALL contain the default configuration values

#### Scenario: Sending custom voice configuration

- **GIVEN** a connected `TTSClient` with `voice_id="emma"` set
- **WHEN** calling `configure()`
- **THEN** a `ConfigMessage` SHALL be sent with the custom voice_id

#### Scenario: Sending custom format configuration

- **GIVEN** a connected `TTSClient` with `output_format="pcm_int16"` set
- **WHEN** calling `configure()`
- **THEN** a `ConfigMessage` SHALL be sent with the custom output format

---

### Requirement: Text message sending

The system SHALL provide methods for sending text to be synthesized.

#### Scenario: Sending text for synthesis

- **GIVEN** a connected `TTSClient`
- **WHEN** calling `synthesize("Hello world")`
- **THEN** a `TextMessage` SHALL be sent to the server
- **AND** the message data SHALL contain the text "Hello world"
- **AND** the message SHALL include the session_id

#### Scenario: Empty text handling

- **GIVEN** a connected `TTSClient`
- **WHEN** calling `synthesize("")`
- **THEN** the system SHALL raise a `ConfigurationError`
- **AND** the error message SHALL indicate that text cannot be empty

---

### Requirement: Streaming audio synthesis

The system SHALL provide an async generator for streaming audio chunks.

#### Scenario: Streaming yields audio chunks

- **GIVEN** a connected `TTSClient`
- **WHEN** iterating over `synthesize("Hello world")`
- **THEN** the system SHALL yield `AudioChunk` objects as they arrive
- **AND** each chunk SHALL contain:
  - `data: bytes` - raw audio data
  - `format: str` - audio format (e.g., "pcm_int16")
  - `sample_rate: int` - sample rate in Hz
  - `is_final: bool` - whether this is the final chunk

#### Scenario: Streaming handles multiple chunks

- **GIVEN** a long text input
- **WHEN** iterating over `synthesize(text)`
- **THEN** the system SHALL yield multiple audio chunks
- **AND** all chunks except the last SHALL have `is_final=False`
- **AND** the final chunk SHALL have `is_final=True`

#### Scenario: Streaming stops on EOS

- **GIVEN** an active synthesis stream
- **WHEN** the server sends an EOS message
- **THEN** the iteration SHALL complete
- **AND** the generator SHALL exit

---

### Requirement: Full audio synthesis

The system SHALL provide a method to synthesize and return complete audio.

#### Scenario: Synthesize returns complete audio

- **GIVEN** a connected `TTSClient`
- **WHEN** calling `synthesize_full("Hello world")`
- **THEN** the system SHALL collect all audio chunks
- **AND** combine them into a single bytes object
- **AND** return the complete audio data

---

### Requirement: File output synthesis

The system SHALL provide a method to synthesize and save audio to a file.

#### Scenario: Synthesize to WAV file

- **GIVEN** a connected `TTSClient`
- **WHEN** calling `synthesize_to_file("Hello world", "output.wav")`
- **THEN** the system SHALL collect all audio chunks
- **AND** combine them into a single bytes object
- **AND** create a WAV file at "output.wav"
- **AND** the file SHALL contain:
  - Proper WAV headers
  - The audio data at 24kHz, 16-bit, mono

#### Scenario: Overwrite existing file

- **GIVEN** an existing file at the output path
- **WHEN** calling `synthesize_to_file(text, output_path)`
- **THEN** the system SHALL overwrite the existing file

---

### Requirement: Message handler registration

The system SHALL allow users to register custom message handlers.

#### Scenario: Registering AUDIO message handler

- **GIVEN** a `TTSClient` instance
- **WHEN** calling `on_message(MessageType.AUDIO, handler_function)`
- **THEN** the handler SHALL be called for each AUDIO message received
- **AND** the handler SHALL receive the `AudioMessage` object

#### Scenario: Registering EOS message handler

- **GIVEN** a `TTSClient` instance
- **WHEN** calling `on_message(MessageType.EOS, handler_function)`
- **THEN** the handler SHALL be called when synthesis is complete
- **AND** the handler SHALL receive the `EOSMessage` object

#### Scenario: Registering ERROR message handler

- **GIVEN** a `TTSClient` instance
- **WHEN** calling `on_message(MessageType.ERROR, handler_function)`
- **THEN** the handler SHALL be called for each ERROR message
- **AND** the handler SHALL receive the `ErrorMessage` object

---

### Requirement: Error handling and recovery

The system SHALL handle errors gracefully with explicit exception types.

#### Scenario: Connection failure

- **GIVEN** a `TTSClient` attempting to connect
- **WHEN** the connection fails
- **THEN** a `ConnectionError` SHALL be raised
- **AND** the error message SHALL describe the failure

#### Scenario: Server error during synthesis

- **GIVEN** an active synthesis session
- **WHEN** the server sends an ERROR message
- **THEN** a `ServerError` SHALL be raised
- **AND** the error SHALL include the server's error code and details

#### Scenario: Timeout waiting for audio

- **GIVEN** a synthesis in progress
- **WHEN** no audio is received within the timeout period
- **THEN** the streaming iteration SHALL raise a `TimeoutError`

#### Scenario: Invalid voice ID

- **GIVEN** a `TTSClient` configured with an invalid voice_id
- **WHEN** synthesis is attempted
- **THEN** the server SHALL return an error
- **AND** a `ServerError` SHALL be raised

---

### Requirement: Automatic reconnection

The system SHALL automatically reconnect with exponential backoff on connection failure.

#### Scenario: Reconnection on transient failure

- **GIVEN** a `TTSClient` that loses connection
- **WHEN** the failure is transient (network blip)
- **THEN** the system SHALL attempt to reconnect
- **AND** use exponential backoff starting at 1 second
- **AND** cap the maximum delay at 30 seconds

#### Scenario: Reconnection failure after max delay

- **GIVEN** a `TTSClient` unable to reconnect
- **WHEN** the delay reaches 30 seconds
- **THEN** the system SHALL stop reconnection attempts
- **AND** raise a `ConnectionError`

---

### Requirement: Audio format consistency

The system SHALL ensure consistent audio format across all output methods.

#### Scenario: Sample rate consistency

- **GIVEN** a `TTSClient` with default configuration
- **WHEN** audio is received from the server
- **THEN** the audio SHALL always be at 24000 Hz sample rate

#### Scenario: Format consistency

- **GIVEN** a `TTSClient` with `output_format="pcm_int16"`
- **WHEN** audio chunks are received
- **THEN** all chunks SHALL contain 16-bit PCM data
- **AND** the data SHALL be signed little-endian integers

#### Scenario: Channel consistency

- **GIVEN** a `TTSClient` with default configuration
- **WHEN** audio is received
- **THEN** the audio SHALL always be mono (1 channel)

---

### Requirement: Synthesis timeout handling

The system SHALL handle timeouts during synthesis gracefully.

#### Scenario: Timeout during streaming

- **GIVEN** an active streaming synthesis
- **WHEN** no audio chunk is received for the timeout period
- **THEN** the system SHALL raise a `TimeoutError`
- **AND** the connection SHALL remain open for retry

#### Scenario: Configurable timeout

- **GIVEN** a `TTSClient` with `timeout=60.0`
- **WHEN** waiting for audio chunks
- **THEN** the system SHALL use the configured timeout value

---

## AudioChunk Reference

### Chunk Structure

```python
@dataclass
class AudioChunk:
    data: bytes           # Raw audio data
    format: str           # Audio format (e.g., "pcm_int16")
    sample_rate: int      # Sample rate in Hz
    is_final: bool        # True if this is the final chunk
```

### Chunk Behavior

| Property | Description |
|----------|-------------|
| `data` | Raw PCM audio bytes, base64-decoded if JSON encoding |
| `format` | Always "pcm_int16" for current server implementation |
| `sample_rate` | Always 24000 Hz for current server implementation |
| `is_final` | True only for the last chunk in the stream |

---

## Audio Format Reference

### Output Format Specifications

| Parameter | Value |
|-----------|-------|
| Sample Rate | 24000 Hz |
| Channels | 1 (mono) |
| Bit Depth | 16-bit signed PCM |
| Byte Order | Little-endian |
| Bytes per Sample | 2 |

### WAV File Format

When saving to WAV, the file SHALL contain:
- RIFF header
- WAVE format
- fmt chunk with PCM format tag
- data chunk with audio samples

### Audio Duration Calculation

```
duration_seconds = bytes_length / (sample_rate × channels × bytes_per_sample)
duration_seconds = bytes_length / (24000 × 1 × 2) = bytes_length / 48000
```

Example: 96000 bytes = 2 seconds of audio