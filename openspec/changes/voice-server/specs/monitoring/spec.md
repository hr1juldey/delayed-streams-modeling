# Monitoring Specification

## ADDED Requirements

### Requirement: Health check endpoint
The system SHALL provide a `/health` endpoint that returns the server health status.

#### Scenario: Health check when server is healthy
- **WHEN** a client GETs `/health`
- **AND** the server is running normally
- **THEN** the server returns HTTP 200 OK
- **AND** the response includes `{"status": "ok"}`
- **AND** the response includes model status information

#### Scenario: Health check when server is unhealthy
- **WHEN** a client GETs `/health`
- **AND** the server has a critical failure (e.g., model not loaded)
- **THEN** the server returns HTTP 503 Service Unavailable
- **AND** the response includes error details

### Requirement: Prometheus metrics endpoint
The system SHALL provide a `/metrics` endpoint that returns metrics in Prometheus text format.

#### Scenario: Get Prometheus metrics
- **WHEN** a client GETs `/metrics`
- **THEN** the server returns metrics in Prometheus text format
- **AND** the metrics include active_sessions, request latency, model status, and error rates
- **AND** the response can be scraped by Prometheus

### Requirement: Active sessions metric
The system SHALL track and report the number of active WebSocket sessions.

#### Scenario: Report active session count
- **WHEN** the `/metrics` endpoint is queried
- **THEN** the server includes `active_sessions` gauge metric
- **AND** the metric shows current number of active sessions
- **AND** the metric is labeled by session type (stt, tts)

### Requirement: Request latency metric
The system SHALL track and report request latency for STT and TTS processing.

#### Scenario: Report STT latency
- **WHEN** the `/metrics` endpoint is queried
- **THEN** the server includes `stt_request_latency_ms` histogram metric
- **AND** the metric shows latency distribution for STT requests
- **AND** the metric includes buckets for target latency (200ms) and higher

#### Scenario: Report TTS latency
- **WHEN** the `/metrics` endpoint is queried
- **THEN** the server includes `tts_request_latency_ms` histogram metric
- **AND** the metric shows latency distribution for TTS requests

### Requirement: Model status metric
The system SHALL track and report the loading status of STT and TTS models.

#### Scenario: Report model status
- **WHEN** the `/metrics` endpoint is queried
- **THEN** the server includes `model_status` gauge metric
- **AND** the metric is labeled by model name (stt_model, tts_model)
- **AND** the metric value is 1 if loaded, 0 if not loaded
- **AND** the metric includes the current model name as a label

### Requirement: Error rate metric
The system SHALL track and report error rates for processing failures.

#### Scenario: Report error rates
- **WHEN** the `/metrics` endpoint is queried
- **THEN** the server includes `error_total` counter metric
- **AND** the metric is labeled by error type (model_error, audio_error, protocol_error)
- **AND** the metric increments with each error occurrence

### Requirement: WebSocket connection metric
The system SHALL track WebSocket connection lifecycle events.

#### Scenario: Report connection metrics
- **WHEN** the `/metrics` endpoint is queried
- **THEN** the server includes `websocket_connections_total` counter metric
- **AND** the metric is labeled by event type (connected, disconnected, rejected)
- **AND** the metric increments with each connection event

### Requirement: Audio processing metric
The system SHALL track audio processing statistics.

#### Scenario: Report audio metrics
- **WHEN** the `/metrics` endpoint is queried
- **THEN** the server includes `audio_processing_bytes_total` counter metric
- **AND** the metric is labeled by direction (input, output)
- **AND** the metric tracks total audio bytes processed

### Requirement: GPU memory metric
The system SHALL track GPU memory usage for STT model operations.

#### Scenario: Report GPU memory
- **WHEN** the `/metrics` endpoint is queried
- **AND** a GPU is available
- **THEN** the server includes `gpu_memory_bytes` gauge metric
- **AND** the metric shows current GPU memory allocation
- **AND** the metric is labeled by GPU device ID

### Requirement: Session timeout metric
The system SHALL track session timeout events.

#### Scenario: Report session timeouts
- **WHEN** the `/metrics` endpoint is queried
- **THEN** the server includes `session_timeouts_total` counter metric
- **AND** the metric increments when a session times out due to inactivity
- **AND** the metric is labeled by timeout reason

### Requirement: Structured JSON logging
The system SHALL output logs in structured JSON format to stdout for integration with logging systems.

#### Scenario: Output structured logs
- **WHEN** the server logs any event (info, warning, error)
- **THEN** the log output is in JSON format
- **AND** the JSON includes timestamp, level, message, and context fields
- **AND** the logs can be parsed by JSON log aggregators

### Requirement: File logging for AI agents
The system SHALL support detailed file logging with rotation for debugging AI agent interactions.

#### Scenario: Write to log file
- **WHEN** file logging is configured
- **THEN** the server writes detailed logs to the configured log file
- **AND** the logs include request/response details, timestamps, and session IDs
- **AND** the log files rotate when they reach the configured size limit
