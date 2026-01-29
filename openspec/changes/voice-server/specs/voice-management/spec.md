# Voice Management Specification

## ADDED Requirements

### Requirement: Upload voice audio file
The system SHALL accept audio file uploads (WAV, MP3) and automatically export them to .safetensors format for Pocket TTS.

#### Scenario: Successful voice upload
- **WHEN** a client POSTs an audio file to `/api/v1/voice/upload`
- **THEN** the server validates the file format
- **AND** the server exports the audio to .safetensors format using Pocket TTS
- **AND** the server stores the .safetensors file in the configured voices_path
- **AND** the server returns a voice_id to the client

#### Scenario: Invalid file format
- **WHEN** a client uploads an unsupported file format
- **THEN** the server returns an error message indicating supported formats

#### Scenario: Export failure
- **WHEN** the Pocket TTS export process fails
- **THEN** the server returns an error message with failure details

### Requirement: List available voices
The system SHALL provide an endpoint to list all available voices stored in the voices_path directory.

#### Scenario: List all voices
- **WHEN** a client GETs `/api/v1/voice/list`
- **THEN** the server returns a list of all available voices
- **AND** each voice includes voice_id, name, and metadata

#### Scenario: Empty voice list
- **WHEN** no voices are stored in the voices_path
- **THEN** the server returns an empty list
- **AND** the server returns HTTP 200 OK

### Requirement: Switch active voice
The system SHALL support switching the globally active default voice during runtime.

#### Scenario: Switch to valid voice
- **WHEN** a client POSTs to `/api/v1/voice/switch` with a valid voice_id
- **THEN** the server updates the global default voice
- **AND** the server confirms the voice switch
- **AND** subsequent TTS requests use the new voice

#### Scenario: Switch to invalid voice
- **WHEN** a client POSTs to `/api/v1/voice/switch` with an invalid voice_id
- **THEN** the server returns an error message
- **AND** the server continues using the current voice

### Requirement: Delete voice
The system SHALL support deletion of voice files from the voices_path directory.

#### Scenario: Delete existing voice
- **WHEN** a client DELETEs `/api/v1/voice/{voice_id}` for an existing voice
- **THEN** the server removes the .safetensors file from storage
- **AND** the server confirms the deletion
- **AND** the voice is no longer available for use

#### Scenario: Delete active voice
- **WHEN** a client attempts to delete the currently active voice
- **THEN** the server returns a warning message
- **AND** the server requires confirmation before deletion
- **AND** upon confirmation, the server deletes the voice and reverts to default voice

#### Scenario: Delete non-existent voice
- **WHEN** a client DELETEs `/api/v1/voice/{voice_id}` for a non-existent voice
- **THEN** the server returns HTTP 404 Not Found

### Requirement: Get voice details
The system SHALL provide detailed metadata for a specific voice.

#### Scenario: Get voice metadata
- **WHEN** a client GETs `/api/v1/voice/{voice_id}` for an existing voice
- **THEN** the server returns detailed voice metadata
- **AND** the metadata includes voice_id, name, format, duration, and creation timestamp

#### Scenario: Voice not found
- **WHEN** a client GETs `/api/v1/voice/{voice_id}` for a non-existent voice
- **THEN** the server returns HTTP 404 Not Found

### Requirement: Voice storage configuration
The system SHALL store voice files in the configured voices_path directory.

#### Scenario: Default voices path
- **WHEN** no custom voices_path is configured
- **THEN** the server stores voices in `./data/voices/`

#### Scenario: Custom voices path
- **WHEN** a custom voices_path is configured via environment variable
- **THEN** the server stores voices in the configured path
