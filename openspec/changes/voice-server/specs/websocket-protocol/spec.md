# WebSocket Protocol Specification

## ADDED Requirements

### Requirement: Message format types
The system SHALL support typed messages including Audio, Text, Error, EOS (End of Stream), and Config types.

#### Scenario: Audio message type
- **WHEN** the client sends audio data
- **THEN** the message includes `type: "Audio"` and PCM data in the `data` field

#### Scenario: Text message type
- **WHEN** the server sends transcription results
- **THEN** the message includes `type: "Text"` and text content in the `data` field

#### Scenario: Error message type
- **WHEN** an error occurs during processing
- **THEN** the server sends a message with `type: "Error"` and error details

#### Scenario: EOS message type
- **WHEN** a stream completes (STT final result or TTS synthesis complete)
- **THEN** the server sends a message with `type: "Eos"` to signal completion

#### Scenario: Config message type
- **WHEN** the client sends configuration options
- **THEN** the message includes `type: "Config"` and configuration parameters

### Requirement: Message encoding support
The system SHALL support both JSON and MessagePack encoding for WebSocket messages.

#### Scenario: JSON encoding
- **WHEN** the client uses JSON encoding (indicated by content-type or config)
- **THEN** the server encodes messages in JSON format
- **AND** the server decodes incoming JSON messages

#### Scenario: MessagePack encoding
- **WHEN** the client uses MessagePack encoding (default, more efficient for binary data)
- **THEN** the server encodes messages in MessagePack format
- **AND** the server decodes incoming MessagePack messages

### Requirement: Session ID in messages
The system SHALL require session_id in all messages for proper routing and state management.

#### Scenario: Include session ID
- **WHEN** any message is sent (client or server)
- **THEN** the message includes a `session_id` field
- **AND** the session_id is used for message routing

#### Scenario: Message without session ID
- **WHEN** a message arrives without a session_id
- **THEN** the server sends an error message
- **AND** the server requests the client to include session_id

### Requirement: Timestamp in messages
The system SHALL include timestamp in messages for timing and debugging purposes.

#### Scenario: Include timestamp
- **WHEN** the server sends any message
- **THEN** the message includes a `timestamp` field
- **AND** the timestamp is in Unix time format

### Requirement: Config message handling
The system SHALL process configuration messages to set session parameters.

#### Scenario: Receive config message
- **WHEN** the client sends a Config message with parameters
- **THEN** the server updates the session configuration
- **AND** the server applies new settings (streaming mode, VAD mode, output format, etc.)
- **AND** the server confirms the configuration was applied

#### Scenario: Invalid config parameter
- **WHEN** the client sends a Config message with invalid parameter
- **THEN** the server sends an error message
- **AND** the server indicates which parameter was invalid
- **AND** the server continues using previous valid configuration

### Requirement: Error message handling
The system SHALL send detailed error messages when errors occur during processing.

#### Scenario: Send error with details
- **WHEN** an error occurs (e.g., invalid audio format, model not loaded)
- **THEN** the server sends an Error message with error code and description
- **AND** the client can take appropriate action based on the error

#### Scenario: Recoverable error
- **WHEN** a recoverable error occurs (e.g., temporary processing failure)
- **THEN** the server sends an Error message
- **AND** the server keeps the WebSocket connection open
- **AND** the client can retry the operation

#### Scenario: Fatal error
- **WHEN** a fatal error occurs (e.g., authentication failure, model load failure)
- **THEN** the server sends an Error message
- **AND** the server closes the WebSocket connection
- **AND** the error message indicates the connection will close

### Requirement: Bidirectional communication
The system SHALL support full-duplex bidirectional communication over WebSocket.

#### Scenario: Simultaneous send and receive
- **WHEN** both client and server are sending messages simultaneously
- **THEN** the server processes incoming messages while sending outgoing messages
- **AND** neither direction blocks the other

### Requirement: Message ordering
The system SHALL maintain message order within each direction (client-to-server and server-to-client).

#### Scenario: Process messages in order
- **WHEN** multiple messages arrive from the client
- **THEN** the server processes them in the order received
- **AND** the server sends responses in the appropriate order

### Requirement: WebSocket compression
The system SHALL support configurable WebSocket compression (permessage-deflate).

#### Scenario: Compression enabled
- **WHEN** `websocket_compression` is true
- **THEN** the server enables permessage-deflate compression
- **AND** messages are compressed for transmission

#### Scenario: Compression disabled
- **WHEN** `websocket_compression` is false
- **THEN** the server sends messages without compression
- **AND** this reduces latency at the cost of bandwidth

### Requirement: Heartbeat/ping messages
The system SHALL support configurable heartbeat intervals for connection health monitoring.

#### Scenario: Send periodic ping
- **WHEN** `heartbeat_interval_seconds` is configured (e.g., 30 seconds)
- **THEN** the server sends WebSocket ping frames at the configured interval
- **AND** the server expects pong responses from the client

#### Scenario: Detect stale connection
- **WHEN** the client does not respond to ping within timeout
- **THEN** the server considers the connection stale
- **AND** the server closes the connection
- **AND** the server cleans up session resources
