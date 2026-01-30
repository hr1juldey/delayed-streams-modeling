# WebSocket Protocol Specification

**Version:** 1.0

## Purpose

Defines the WebSocket message protocol used for communication between voice client SDK and voice server. Specifies message types, encoding formats (JSON and MessagePack), and serialization requirements for audio streaming, text transcription, and error handling.

---

## Requirements

### Requirement: Message type enumeration

The system SHALL provide a `MessageType` enum defining all supported WebSocket message types.

#### Scenario: Enum contains all message types

- **WHEN** accessing the `MessageType` enum
- **THEN** the following values SHALL be available:
  - `AUDIO` - for audio data messages
  - `TEXT` - for text data messages
  - `ERROR` - for error messages
  - `EOS` - for end-of-stream markers
  - `CONFIG` - for configuration messages
  - `HEARTBEAT` - for keepalive messages

---

### Requirement: Base message structure

The system SHALL provide a `Message` dataclass representing all WebSocket messages.

#### Scenario: Message contains required fields

- **WHEN** creating a `Message` instance
- **THEN** it SHALL have the following fields:
  - `type: MessageType` - the message type
  - `data: Any` - the message payload
  - `session_id: str` - unique session identifier
  - `timestamp: float | None` - Unix timestamp (auto-generated if None)
  - `metadata: dict | None` - optional additional metadata

#### Scenario: Timestamp auto-generation

- **WHEN** a message is created with `timestamp=None`
- **THEN** the system SHALL automatically set `timestamp` to the current Unix time

---

### Requirement: Audio message type

The system SHALL provide an `AudioMessage` dataclass for audio data messages.

#### Scenario: Audio message contains audio metadata

- **WHEN** creating an `AudioMessage` instance
- **THEN** it SHALL extend `Message` and add the following fields:
  - `format: str` - audio format (default: "pcm_int16")
  - `sample_rate: int` - sample rate in Hz (default: 24000)
  - `channels: int` - number of audio channels (default: 1)

---

### Requirement: Text message type

The system SHALL provide a `TextMessage` dataclass for text data messages.

#### Scenario: Text message contains transcription metadata

- **WHEN** creating a `TextMessage` instance
- **THEN** it SHALL extend `Message` and add the following fields:
  - `is_partial: bool` - whether this is a partial/streaming result (default: False)
  - `is_final: bool` - whether this is the final result in a sequence (default: False)
  - `confidence: float | None` - confidence score for the result

---

### Requirement: Error message type

The system SHALL provide an `ErrorMessage` dataclass for error messages.

#### Scenario: Error message contains error details

- **WHEN** creating an `ErrorMessage` instance
- **THEN** it SHALL extend `Message` and add the following fields:
  - `code: str` - error code for programmatic handling (default: "ERROR")
  - `details: str | None` - detailed error information

---

### Requirement: EOS message type

The system SHALL provide an `EOSMessage` dataclass for end-of-stream markers.

#### Scenario: EOS message contains reason

- **WHEN** creating an `EOSMessage` instance
- **THEN** it SHALL extend `Message` and add the following field:
  - `reason: str | None` - optional reason for ending the stream

---

### Requirement: Config message type

The system SHALL provide a `ConfigMessage` dataclass for configuration messages.

#### Scenario: Config message contains configuration data

- **WHEN** creating a `ConfigMessage` instance
- **THEN** it SHALL extend `Message` with `data` typed as `dict`
- **AND** it SHALL provide a `get_config(key, default)` method for accessing configuration values

---

### Requirement: JSON message encoding

The system SHALL provide a `JSONEncoder` class for encoding/decoding messages in JSON format.

#### Scenario: Encoding audio messages base64-encodes audio data

- **GIVEN** an `AudioMessage` with audio data as bytes
- **WHEN** encoding with `JSONEncoder`
- **THEN** the audio data SHALL be base64-encoded as an ASCII string
- **AND** the message SHALL serialize to valid JSON

#### Scenario: Decoding audio messages base64-decodes audio data

- **GIVEN** a JSON message with base64-encoded audio data
- **WHEN** decoding with `JSONEncoder`
- **THEN** the audio data SHALL be decoded back to bytes

#### Scenario: Message type conversion

- **GIVEN** a decoded JSON message with `type` as string
- **WHEN** the message type string matches a `MessageType` value
- **THEN** the `type` field SHALL be converted to the `MessageType` enum

#### Scenario: Invalid JSON raises ProtocolError

- **GIVEN** invalid JSON bytes
- **WHEN** attempting to decode with `JSONEncoder`
- **THEN** a `ProtocolError` SHALL be raised with a descriptive message

---

### Requirement: MessagePack message encoding

The system SHALL provide a `MessagePackEncoder` class for encoding/decoding messages in MessagePack format.

#### Scenario: Encoding preserves binary audio data

- **GIVEN** an `AudioMessage` with audio data as bytes
- **WHEN** encoding with `MessagePackEncoder`
- **THEN** the audio data SHALL be sent as raw binary bytes (not base64-encoded)

#### Scenario: Message type conversion

- **GIVEN** a decoded MessagePack message with `type` as string
- **WHEN** the message type string matches a `MessageType` value
- **THEN** the `type` field SHALL be converted to the `MessageType` enum

#### Scenario: Invalid MessagePack raises ProtocolError

- **GIVEN** invalid MessagePack bytes
- **WHEN** attempting to decode with `MessagePackEncoder`
- **THEN** a `ProtocolError` SHALL be raised with a descriptive message

---

### Requirement: Encoder factory function

The system SHALL provide a `get_encoder(encoding)` function to obtain encoder instances.

#### Scenario: Getting JSON encoder

- **WHEN** calling `get_encoder("json")`
- **THEN** a `JSONEncoder` instance SHALL be returned

#### Scenario: Getting MessagePack encoder

- **WHEN** calling `get_encoder("msgpack")`
- **THEN** a `MessagePackEncoder` instance SHALL be returned

#### Scenario: Invalid encoding raises ValueError

- **GIVEN** an encoding value other than "json" or "msgpack"
- **WHEN** calling `get_encoder(encoding)`
- **THEN** a `ValueError` SHALL be raised

---

### Requirement: Convenience message constructors

The system SHALL provide convenience functions for creating common message types.

#### Scenario: Creating audio messages

- **WHEN** calling `create_audio_message(data, session_id, format, sample_rate, channels)`
- **THEN** an `AudioMessage` instance SHALL be returned with the specified parameters

#### Scenario: Creating text messages

- **WHEN** calling `create_text_message(data, session_id, is_partial, is_final, confidence)`
- **THEN** a `TextMessage` instance SHALL be returned with the specified parameters

#### Scenario: Creating config messages

- **WHEN** calling `create_config_message(data, session_id)`
- **THEN** a `ConfigMessage` instance SHALL be returned with the specified parameters

#### Scenario: Creating EOS messages

- **WHEN** calling `create_eos_message(session_id, reason)`
- **THEN** an `EOSMessage` instance SHALL be returned with the specified parameters

---

## Message Format Reference

### Message Structure

All messages share this base structure:

```json
{
  "type": "Audio|Text|Error|Eos|Config|Heartbeat",
  "data": "<payload>",
  "session_id": "<uuid>",
  "timestamp": 1234567890.123,
  "metadata": {}
}
```

### Audio Message Format

```json
{
  "type": "Audio",
  "data": "<base64-encoded-bytes>",  // JSON mode only
  "session_id": "<uuid>",
  "format": "pcm_int16",
  "sample_rate": 24000,
  "channels": 1
}
```

### Text Message Format

```json
{
  "type": "Text",
  "data": "transcribed text or text to synthesize",
  "session_id": "<uuid>",
  "is_partial": false,
  "is_final": true,
  "confidence": 0.95
}
```

### Error Message Format

```json
{
  "type": "Error",
  "data": {"message": "Error description"},
  "session_id": "<uuid>",
  "code": "ERROR_CODE",
  "details": "Additional details"
}
```

### EOS Message Format

```json
{
  "type": "Eos",
  "data": null,
  "session_id": "<uuid>",
  "reason": "synthesis_complete"
}
```

### Config Message Format

```json
{
  "type": "Config",
  "data": {
    "key": "value"
  },
  "session_id": "<uuid>"
}
```
