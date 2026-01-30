# STT Client Specification

**Version:** 1.0

## Purpose

Defines the Speech-to-Text client for transcribing audio via WebSocket. Provides automatic audio validation, chunking, streaming transcription, and one-shot transcription modes.

---

## Requirements

### Requirement: STTClient initialization

The system SHALL provide an `STTClient` class for Speech-to-Text transcription via WebSocket.

#### Scenario: Creating client with default parameters

- **WHEN** creating an `STTClient` with no parameters
- **THEN** the following defaults SHALL be used:
  - `url: "ws://localhost:16000/api/v1/ws/stt"`
  - `encoding: "json"`
  - `timeout: 30.0` seconds
  - `api_key: None`

#### Scenario: Creating client with custom parameters

- **WHEN** creating an `STTClient(url="ws://example.com", encoding="msgpack", timeout=60.0)`
- **THEN** the client SHALL use the specified parameters

#### Scenario: Default configuration values

- **WHEN** an `STTClient` is initialized
- **THEN** the following default config SHALL be set:
  - `streaming_mode: "both"`
  - `input_format: "int16"`

---

### Requirement: Async context manager support

The system SHALL support `async with` for automatic connection lifecycle management.

#### Scenario: Context manager connects on enter

- **GIVEN** an `STTClient` instance
- **WHEN** entering the context manager with `async with STTClient() as stt`
- **THEN** the system SHALL automatically connect to the WebSocket server
- **AND** a unique `session_id` SHALL be generated
- **AND** the client instance SHALL be returned

#### Scenario: Context manager disconnects on exit

- **GIVEN** an active `STTClient` connection within a context manager
- **WHEN** exiting the context manager (normally or via exception)
- **THEN** the system SHALL gracefully close the WebSocket connection
- **AND** all resources SHALL be cleaned up

---

### Requirement: Configuration message sending

The system SHALL provide a `configure()` method for sending initial configuration to the server.

#### Scenario: Sending default configuration

- **GIVEN** a connected `STTClient`
- **WHEN** calling `configure()`
- **THEN** a `ConfigMessage` SHALL be sent to the server
- **AND** the message SHALL contain the default configuration values

#### Scenario: Sending custom configuration

- **GIVEN** a connected `STTClient` with custom config set
- **WHEN** calling `configure()`
- **THEN** a `ConfigMessage` SHALL be sent with the custom configuration values

---

### Requirement: Audio file loading and validation

The system SHALL provide methods for loading and validating audio files.

#### Scenario: Loading WAV files

- **GIVEN** a valid WAV file path
- **WHEN** passing the path to `send_audio()`
- **THEN** the system SHALL parse the WAV header
- **AND** extract the PCM audio data
- **AND** return the sample rate from the file

#### Scenario: Validating sample rate

- **GIVEN** audio data with sample rate
- **WHEN** the sample rate is not 16000 or 24000 Hz
- **THEN** the system SHALL raise an `AudioFormatError`
- **AND** the error message SHALL indicate supported rates

#### Scenario: Validating channel count

- **GIVEN** a WAV file
- **WHEN** the file has more than 1 channel
- **THEN** the system SHALL raise an `AudioFormatError`
- **AND** the error message SHALL suggest conversion to mono

#### Scenario: Validating bit depth

- **GIVEN** a WAV file
- **WHEN** the file is not 16-bit (2 bytes per sample)
- **THEN** the system SHALL raise an `AudioFormatError`
- **AND** the error message SHALL indicate expected bit depth

---

### Requirement: Audio chunking and sending

The system SHALL automatically chunk audio data and send it to the server.

#### Scenario: Calculating optimal chunk size

- **GIVEN** a sample rate of 24000 Hz and `chunk_size_ms=80`
- **WHEN** calculating the chunk size
- **THEN** the system SHALL calculate: `24000 * 80 / 1000 * 2 = 3840` bytes

#### Scenario: Sending audio chunks

- **GIVEN** a connected `STTClient` with audio data
- **WHEN** calling `send_audio(audio_bytes, chunk_size_ms=80)`
- **THEN** the audio SHALL be split into chunks of the calculated size
- **AND** each chunk SHALL be sent as an `AudioMessage`
- **AND** each message SHALL include the sample rate

#### Scenario: Accepting different audio inputs

- **GIVEN** an `STTClient`
- **WHEN** calling `send_audio()` with:
  - a file path (str or Path) - SHALL load and validate the file
  - raw bytes - SHALL use directly with default sample rate
- **THEN** the system SHALL handle each input type appropriately

---

### Requirement: End-of-stream signaling

The system SHALL provide a method to signal the end of audio input.

#### Scenario: Sending EOS message

- **GIVEN** a connected `STTClient`
- **WHEN** calling `send_eos()`
- **THEN** an `EOSMessage` SHALL be sent to the server
- **AND** the message SHALL include the session_id

---

### Requirement: Transcription result retrieval

The system SHALL provide methods for retrieving transcription results.

#### Scenario: Getting final transcription

- **GIVEN** a connected `STTClient` that has sent audio and EOS
- **WHEN** calling `get_transcription(timeout=30.0)`
- **THEN** the system SHALL wait for the final transcription result
- **AND** return the complete transcribed text as a string
- **AND** raise `TimeoutError` if no result within the timeout

#### Scenario: Streaming transcription results

- **GIVEN** a connected `STTClient`
- **WHEN** iterating over `stream_transcription()`
- **THEN** the system SHALL yield `TranscriptionResult` objects as they arrive
- **AND** each result SHALL contain:
  - `text: str` - the transcribed text
  - `is_final: bool` - whether this is a final result
  - `confidence: float` - confidence score
- **AND** the iteration SHALL complete after the final result

---

### Requirement: One-shot transcription convenience

The system SHALL provide a convenience method for complete transcription workflow.

#### Scenario: Transcribe method combines all steps

- **GIVEN** a connected `STTClient`
- **WHEN** calling `transcribe("speech.wav", timeout=30.0)`
- **THEN** the system SHALL:
  1. Load and validate the audio file
  2. Send audio chunks to the server
  3. Send EOS message
  4. Wait for and return the final transcription
- **AND** return the transcribed text as a string

---

### Requirement: Message handler registration

The system SHALL allow users to register custom message handlers.

#### Scenario: Registering TEXT message handler

- **GIVEN** an `STTClient` instance
- **WHEN** calling `on_message(MessageType.TEXT, handler_function)`
- **THEN** the handler SHALL be called for each TEXT message received
- **AND** the handler SHALL receive the `TextMessage` object

#### Scenario: Registering ERROR message handler

- **GIVEN** an `STTClient` instance
- **WHEN** calling `on_message(MessageType.ERROR, handler_function)`
- **THEN** the handler SHALL be called for each ERROR message received
- **AND** the handler SHALL receive the `ErrorMessage` object

#### Scenario: Multiple handlers per message type

- **GIVEN** an `STTClient` with multiple handlers registered for TEXT messages
- **WHEN** a TEXT message is received
- **THEN** all registered handlers SHALL be called in order

---

### Requirement: Error handling and recovery

The system SHALL handle errors gracefully with explicit exception types.

#### Scenario: Connection failure

- **GIVEN** an `STTClient` attempting to connect
- **WHEN** the connection fails
- **THEN** a `ConnectionError` SHALL be raised
- **AND** the error message SHALL describe the failure

#### Scenario: Invalid audio format

- **GIVEN** audio data with unsupported format
- **WHEN** calling `send_audio()`
- **THEN** an `AudioFormatError` SHALL be raised
- **AND** the error message SHALL describe the issue and suggest fixes

#### Scenario: Server error response

- **GIVEN** an active transcription session
- **WHEN** the server sends an ERROR message
- **THEN** a `ServerError` SHALL be raised
- **AND** the error SHALL include the server's error code and details

#### Scenario: Timeout waiting for result

- **GIVEN** a transcription in progress
- **WHEN** no result is received within the timeout period
- **THEN** a `TimeoutError` SHALL be raised

---

### Requirement: Automatic reconnection

The system SHALL automatically reconnect with exponential backoff on connection failure.

#### Scenario: Reconnection on transient failure

- **GIVEN** an `STTClient` that loses connection
- **WHEN** the failure is transient (network blip)
- **THEN** the system SHALL attempt to reconnect
- **AND** use exponential backoff starting at 1 second
- **AND** cap the maximum delay at 30 seconds

#### Scenario: Reconnection failure after max delay

- **GIVEN** an `STTClient` unable to reconnect
- **WHEN** the delay reaches 30 seconds
- **THEN** the system SHALL stop reconnection attempts
- **AND** raise a `ConnectionError`

---

## TranscriptionResult Reference

### Result Structure

```python
@dataclass
class TranscriptionResult:
    text: str           # Transcribed text
    is_final: bool      # True if this is the final result
    confidence: float   # Confidence score (0.0 to 1.0)
```

### Result Behavior

| Property | Description |
|----------|-------------|
| `is_partial` | True if `is_final=False`, indicates streaming intermediate result |
| `is_final` | True for the final complete transcription |
| `confidence` | Server-provided confidence score, 0.0 if not available |

---

## Audio Format Reference

### Supported Formats

| Parameter | Valid Values | Default |
|-----------|-------------|---------|
| Sample Rate | 16000, 24000 Hz | - |
| Channels | 1 (mono) | Required |
| Bit Depth | 16-bit (int16) | Required |
| Input Types | WAV file path, raw bytes, Path object | - |

### Chunk Size Calculation

```
bytes_per_chunk = (sample_rate × chunk_size_ms / 1000) × 2
```

Examples:
- 16 kHz, 80 ms: 2560 bytes
- 24 kHz, 80 ms: 3840 bytes
- 24 kHz, 100 ms: 4800 bytes
