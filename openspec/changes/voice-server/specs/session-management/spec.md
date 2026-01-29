# Session Management Specification

## ADDED Requirements

### Requirement: Session ID generation
The system SHALL generate unique UUID session IDs for each WebSocket connection.

#### Scenario: Generate session ID on connection
- **WHEN** a client connects to STT or TTS WebSocket
- **THEN** the server generates a unique UUID for the session
- **AND** the server sends the session_id to the client
- **AND** the session_id is used for all subsequent messages

### Requirement: Session history storage
The system SHALL maintain conversation history per session with pluggable storage backends (SQLite default, with option for in-memory).

#### Scenario: Store session history in SQLite
- **WHEN** `storage_backend` is configured as "sqlite"
- **THEN** the server stores session history in SQLite database
- **AND** the database file is located at the configured db_path
- **AND** the server persists conversation turns with timestamps

#### Scenario: Store session history in memory
- **WHEN** `storage_backend` is configured as "memory"
- **THEN** the server stores session history in memory
- **AND** the history is lost when the server restarts

### Requirement: Client-provided history support
The system SHALL accept client-provided conversation history and use it when provided.

#### Scenario: Client provides history
- **WHEN** a client sends conversation history in the initial config message
- **THEN** the server uses the client-provided history for the session
- **AND** the server does not override it with server-stored history
- **AND** required field behavior: warn gracefully if missing

#### Scenario: Client does not provide history
- **WHEN** a client does not send history in the config message
- **AND** history_required is true
- **THEN** the server attempts to load history from the session store
- **AND** if no stored history exists, the server sends a warning
- **AND** the server starts a new session with empty history

### Requirement: Session recovery
The system SHALL allow clients to resume sessions using the same session_id.

#### Scenario: Resume existing session
- **WHEN** a client reconnects with a previously used session_id
- **AND** the session exists in storage
- **THEN** the server resumes the session with existing history
- **AND** the server continues where the session left off

#### Scenario: Resume non-existent session
- **WHEN** a client reconnects with a session_id that doesn't exist
- **THEN** the server creates a new session with the provided session_id
- **AND** the server starts with empty history

### Requirement: Session timeout handling
The system SHALL support configurable session timeout with two modes: no timeout or inactivity timeout.

#### Scenario: No timeout mode
- **WHEN** the session is configured with timeout mode disabled
- **THEN** the server never expires the session due to inactivity
- **AND** the session remains active until client disconnects

#### Scenario: Inactivity timeout mode
- **WHEN** the session is configured with N minutes timeout
- **AND** no activity occurs for N minutes
- **THEN** the server cleans up the session
- **AND** the server frees session resources

#### Scenario: Activity refreshes timeout
- **WHEN** a configured session has activity (message received)
- **THEN** the server resets the inactivity timer
- **AND** the session timeout is recalculated from the last activity

### Requirement: Session activity tracking
The system SHALL track last activity timestamp for each session.

#### Scenario: Update activity on message
- **WHEN** a client sends any message (audio, text, config)
- **THEN** the server updates the session's last_activity timestamp
- **AND** the server uses this timestamp for timeout calculations

### Requirement: Concurrent session limits
The system SHALL enforce a maximum number of concurrent sessions as configured.

#### Scenario: Within session limit
- **WHEN** the number of active sessions is below max_concurrent_sessions
- **THEN** the server accepts new session connections
- **AND** the server continues normal operation

#### Scenario: At session limit
- **WHEN** the number of active sessions equals max_concurrent_sessions
- **THEN** the server rejects new session connections
- **AND** the server returns an error indicating server is at capacity

### Requirement: Session cleanup
The system SHALL periodically clean up expired sessions and free resources.

#### Scenario: Cleanup expired sessions
- **WHEN** the background cleanup task runs
- **THEN** the server identifies sessions with inactivity timeout exceeded
- **AND** the server removes expired sessions from memory
- **AND** the server closes WebSocket connections for expired sessions

### Requirement: Full history per session
The system SHALL maintain complete conversation history for each session, not truncated or summarized.

#### Scenario: Store complete conversation turn
- **WHEN** a client completes an interaction (STT or TTS turn)
- **THEN** the server stores the complete turn with audio input, text output, and metadata
- **AND** the server does not truncate or summarize the history

#### Scenario: Retrieve full history
- **WHEN** a client requests session history or resumes a session
- **THEN** the server provides the complete conversation history
- **AND** no turns are missing or summarized
