# Voice Client Specification

**Version:** 1.0

## ADDED Requirements

### Requirement: VoiceClient initialization

The system SHALL provide a `VoiceClient` class combining STT and TTS capabilities.

#### Scenario: Creating client with default parameters

- **WHEN** creating a `VoiceClient` with no parameters
- **THEN** the following defaults SHALL be used:
  - `stt_url: "ws://localhost:16000/api/v1/ws/stt"`
  - `tts_url: "ws://localhost:16000/api/v1/ws/tts"`
  - `encoding: "json"`
  - `timeout: 30.0` seconds
  - `api_key: None`

#### Scenario: Creating client with custom parameters

- **WHEN** creating `VoiceClient(stt_url="ws://stt.example.com", tts_url="ws://tts.example.com")`
- **THEN** the client SHALL connect STT to the specified STT URL
- **AND** the client SHALL connect TTS to the specified TTS URL

#### Scenario: Creating client with shared URL

- **WHEN** creating `VoiceClient(url="ws://example.com")`
- **THEN** both STT and TTS SHALL connect to the same base URL
- **AND** the STT endpoint SHALL append "/stt"
- **AND** the TTS endpoint SHALL append "/tts"

---

### Requirement: Dual async context manager

The system SHALL support `async with` that manages both STT and TTS connections.

#### Scenario: Context manager connects both clients

- **GIVEN** a `VoiceClient` instance
- **WHEN** entering the context manager with `async with VoiceClient() as voice`
- **THEN** the system SHALL connect the STT client to the STT endpoint
- **AND** the system SHALL connect the TTS client to the TTS endpoint
- **AND** each client SHALL have a unique session_id
- **AND** the VoiceClient instance SHALL be returned

#### Scenario: Context manager disconnects both clients

- **GIVEN** an active `VoiceClient` connection within a context manager
- **WHEN** exiting the context manager (normally or via exception)
- **THEN** the system SHALL close both STT and TTS connections
- **AND** all resources SHALL be cleaned up

#### Scenario: Partial connection failure

- **GIVEN** a `VoiceClient` attempting to connect
- **WHEN** the STT connection succeeds but TTS connection fails
- **THEN** a `ConnectionError` SHALL be raised
- **AND** the STT connection SHALL be cleaned up

---

### Requirement: Full conversation workflow

The system SHALL provide a method for complete STT → Agent → TTS workflow.

#### Scenario: Converse method transcribes input

- **GIVEN** a connected `VoiceClient`
- **WHEN** calling `converse(audio_bytes)`
- **THEN** the audio SHALL be sent to the STT service
- **AND** the system SHALL wait for the transcription result

#### Scenario: Converse method processes with agent

- **GIVEN** a transcription result from STT
- **WHEN** an `agent_callback` is provided
- **THEN** the transcription SHALL be passed to the agent_callback
- **AND** the callback's return value SHALL be used as response text
- **WHEN** no `agent_callback` is provided
- **THEN** a default echo response SHALL be generated: "You said: {transcription}"

#### Scenario: Converse method synthesizes response

- **GIVEN** a response text from the agent callback
- **WHEN** the response text is obtained
- **THEN** the text SHALL be sent to the TTS service
- **AND** the system SHALL collect all audio chunks
- **AND** return the combined audio as bytes

#### Scenario: Converse returns both results

- **GIVEN** a complete conversation cycle
- **WHEN** `converse()` completes
- **THEN** the system SHALL return a tuple: `(transcription: str, response_audio: bytes)`
- **AND** `transcription` SHALL contain the user's speech as text
- **AND** `response_audio` SHALL contain the synthesized response audio

---

### Requirement: Direct client access

The system SHALL provide direct access to underlying STT and TTS clients.

#### Scenario: Accessing STT client

- **GIVEN** a `VoiceClient` instance
- **WHEN** accessing the `stt` attribute
- **THEN** an `STTClient` instance SHALL be returned
- **AND** all STTClient methods SHALL be available

#### Scenario: Accessing TTS client

- **GIVEN** a `VoiceClient` instance
- **WHEN** accessing the `tts` attribute
- **THEN** a `TTSClient` instance SHALL be returned
- **AND** all TTSClient methods SHALL be available

#### Scenario: Using STT directly

- **GIVEN** a connected `VoiceClient`
- **WHEN** calling `voice.stt.transcribe(audio)`
- **THEN** transcription SHALL proceed using only the STT client
- **AND** no TTS synthesis SHALL occur

#### Scenario: Using TTS directly

- **GIVEN** a connected `VoiceClient`
- **WHEN** calling `voice.tts.synthesize_full(text)`
- **THEN** synthesis SHALL proceed using only the TTS client
- **AND** no STT transcription SHALL occur

---

### Requirement: Agent callback interface

The system SHALL support custom agent callbacks for response generation.

#### Scenario: Agent callback receives transcription

- **GIVEN** a `VoiceClient` with an agent callback registered
- **WHEN** STT transcription completes
- **THEN** the agent callback SHALL be called with the transcription text
- **AND** the callback SHALL run in the same async context

#### Scenario: Agent callback returns response text

- **GIVEN** an agent callback function
- **WHEN** the callback returns a string
- **THEN** the string SHALL be used as the TTS input text

#### Scenario: Agent callback may raise exceptions

- **GIVEN** an agent callback function
- **WHEN** the callback raises an exception
- **THEN** the exception SHALL propagate from `converse()`
- **AND** the connection SHALL remain open for retry

#### Scenario: Agent callback can be async

- **GIVEN** an async agent callback function
- **WHEN** the callback is invoked
- **THEN** the system SHALL await the async callback
- **AND** the result SHALL be handled the same as a sync callback

---

### Requirement: Independent session management

The system SHALL maintain independent sessions for STT and TTS.

#### Scenario: Separate session IDs

- **GIVEN** a connected `VoiceClient`
- **WHEN** both clients are connected
- **THEN** `voice.stt._session_id` SHALL contain a unique UUID for STT
- **AND** `voice.tts._session_id` SHALL contain a different UUID for TTS

#### Scenario: Independent configuration

- **GIVEN** a `VoiceClient` instance
- **WHEN** calling `voice.stt.configure()` with STT-specific config
- **AND** calling `voice.tts.configure()` with TTS-specific config
- **THEN** each client SHALL maintain its own configuration
- **AND** configurations SHALL NOT interfere

#### Scenario: Independent message handlers

- **GIVEN** a `VoiceClient` instance
- **WHEN** registering handlers on `voice.stt`
- **AND** registering handlers on `voice.tts`
- **THEN** each client SHALL have its own set of handlers
- **AND** handlers SHALL NOT receive messages from the other client

---

### Requirement: Error propagation

The system SHALL properly propagate errors from both clients.

#### Scenario: STT error propagation

- **GIVEN** a `VoiceClient` in a `converse()` call
- **WHEN** the STT client raises an `AudioFormatError`
- **THEN** the error SHALL propagate from `converse()`
- **AND** no TTS synthesis SHALL be attempted

#### Scenario: TTS error propagation

- **GIVEN** a `VoiceClient` in a `converse()` call
- **WHEN** STT succeeds but TTS raises a `ServerError`
- **THEN** the error SHALL propagate from `converse()`
- **AND** the successful transcription SHALL be lost (user must retry)

#### Scenario: Timeout error propagation

- **GIVEN** a `VoiceClient` with a short timeout configured
- **WHEN** either client times out
- **THEN** a `TimeoutError` SHALL propagate from `converse()`
- **AND** the error message SHALL indicate which client timed out

---

### Requirement: Configuration inheritance

The system SHALL share common configuration between both clients.

#### Scenario: Shared encoding parameter

- **GIVEN** a `VoiceClient(encoding="msgpack")`
- **WHEN** the client connects
- **THEN** both STT and TTS clients SHALL use MessagePack encoding

#### Scenario: Shared timeout parameter

- **GIVEN** a `VoiceClient(timeout=60.0)`
- **WHEN** either client performs operations
- **THEN** both clients SHALL use the 60-second timeout

#### Scenario: Shared API key parameter

- **GIVEN** a `VoiceClient(api_key="secret")`
- **WHEN** connecting to the server
- **THEN** both clients SHALL include the API key in their URLs

---

### Requirement: Conversation streaming mode

The system SHALL support streaming both STT and TTS in a conversation.

#### Scenario: Streaming conversation yields updates

- **GIVEN** a connected `VoiceClient`
- **WHEN** iterating over `converse_stream(audio_bytes, agent_callback)`
- **THEN** the system SHALL yield `ConversationEvent` objects
- **AND** events SHALL include:
  - STT partial results
  - STT final result
  - TTS audio chunks
  - Completion event

#### Scenario: Streaming conversation event types

- **GIVEN** a streaming conversation
- **WHEN** STT produces partial results
- **THEN** the system SHALL yield `ConversationEvent(type="stt_partial", data=result)`
- **WHEN** STT produces final result
- **THEN** the system SHALL yield `ConversationEvent(type="stt_final", data=result)`
- **WHEN** TTS produces audio chunks
- **THEN** the system SHALL yield `ConversationEvent(type="tts_audio", data=chunk)`
- **WHEN** conversation completes
- **THEN** the system SHALL yield `ConversationEvent(type="complete", data=None)`

---

### Requirement: Multiple conversation cycles

The system SHALL support multiple conversation cycles in one session.

#### Scenario: Multiple converse calls

- **GIVEN** a connected `VoiceClient`
- **WHEN** calling `converse(audio1)` then `converse(audio2)`
- **THEN** both calls SHALL complete successfully
- **AND** the same STT and TTS connections SHALL be reused
- **AND** new session IDs SHALL be generated for each call

#### Scenario: Conversation state isolation

- **GIVEN** a `VoiceClient` with an agent callback
- **WHEN** the agent callback maintains state
- **THEN** the state SHALL persist across multiple `converse()` calls
- **AND** each conversation SHALL build on previous state

---

## ConversationEvent Reference

### Event Structure

```python
@dataclass
class ConversationEvent:
    type: str           # Event type: "stt_partial", "stt_final", "tts_audio", "complete"
    data: Any           # Event data (varies by type)
    timestamp: float    # Event timestamp
```

### Event Types

| Type | Data Type | Description |
|------|-----------|-------------|
| `stt_partial` | `TranscriptionResult` | Partial STT result during streaming |
| `stt_final` | `TranscriptionResult` | Final STT transcription |
| `tts_audio` | `AudioChunk` | TTS audio chunk |
| `complete` | `None` | Conversation cycle complete |

---

## Usage Patterns

### Basic Conversation

```python
async with VoiceClient() as voice:
    transcription, response_audio = await voice.converse(
        audio="speech.wav",
        agent_callback=lambda text: f"I heard: {text}"
    )
    print(f"User said: {transcription}")
    # Play response_audio...
```

### Direct Client Access

```python
async with VoiceClient() as voice:
    # STT only
    text = await voice.stt.transcribe("input.wav")

    # TTS only
    audio = await voice.tts.synthesize_full("Hello world")
```

### Streaming Conversation

```python
async with VoiceClient() as voice:
    async for event in voice.converse_stream(
        audio="speech.wav",
        agent_callback=my_agent
    ):
        if event.type == "stt_partial":
            print(f"Partial: {event.data.text}")
        elif event.type == "stt_final":
            print(f"Final: {event.data.text}")
        elif event.type == "tts_audio":
            play_audio_chunk(event.data.data)
        elif event.type == "complete":
            print("Conversation complete")
```

### Stateful Agent

```python
class ConversationAgent:
    def __init__(self):
        self.history = []

    def __call__(self, text: str) -> str:
        self.history.append(text)
        # Generate response based on history...
        return response

async with VoiceClient() as voice:
    agent = ConversationAgent()
    while True:
        audio = await get_user_input()
        transcription, response = await voice.converse(audio, agent_callback=agent)
        play_audio(response)
```