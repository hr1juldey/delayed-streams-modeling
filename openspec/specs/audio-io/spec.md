# Audio I/O Specification

**Version:** 1.0

## Purpose

Defines audio recording and playback capabilities for the voice client SDK. Provides classes for microphone input with silence detection and speaker output with streaming support.

---

## Requirements

### Requirement: AudioRecorder device enumeration

The system SHALL provide an `AudioRecorder` class for recording audio from a microphone.

#### Scenario: Listing available input devices

- **WHEN** calling `AudioRecorder.list_devices()`
- **THEN** the system SHALL return a list of dictionaries
- **AND** each device dictionary SHALL contain:
  - `index: int` - device index
  - `name: str` - device name
  - `channels: int` - maximum input channels
  - `sample_rate: int` - default sample rate

#### Scenario: Only input devices are listed

- **WHEN** listing devices
- **THEN** devices SHALL be filtered to only include those with `max_input_channels > 0`

---

### Requirement: AudioRecorder initialization

The system SHALL allow creating an `AudioRecorder` with configurable parameters.

#### Scenario: Creating recorder with default parameters

- **WHEN** creating an `AudioRecorder` with no parameters
- **THEN** the following defaults SHALL be used:
  - `sample_rate: 24000` Hz
  - `channels: 1` (mono)
  - `device: None` (system default)

#### Scenario: Creating recorder with custom parameters

- **WHEN** creating an `AudioRecorder(sample_rate=16000, channels=2, device=5)`
- **THEN** the recorder SHALL use the specified parameters

---

### Requirement: Fixed-duration recording

The system SHALL provide a `record()` method for recording audio for a fixed duration.

#### Scenario: Recording for specified duration

- **GIVEN** an initialized `AudioRecorder`
- **WHEN** calling `record(duration_seconds=5.0)`
- **THEN** the system SHALL record audio for 5 seconds
- **AND** return a tuple of `(audio_array, sample_rate)`
- **AND** `audio_array` SHALL be a numpy array with dtype `int16`
- **AND** the system SHALL block until recording is complete

#### Scenario: Recording trims silence

- **GIVEN** an `AudioRecorder` with `silence_threshold=0.01`
- **WHEN** calling `record(duration_seconds=5.0)`
- **THEN** the system SHALL trim leading and trailing silence from the recording
- **AND** silence SHALL be defined as samples with absolute value < threshold

---

### Requirement: Streaming audio recording

The system SHALL provide a `record_stream()` async method for recording audio in chunks.

#### Scenario: Streaming records until silence

- **GIVEN** an initialized `AudioRecorder`
- **WHEN** iterating over `record_stream(chunk_size_ms=80, silence_threshold=0.01, silence_duration_ms=1000)`
- **THEN** the system SHALL yield audio chunks as bytes
- **AND** each chunk SHALL contain approximately 80ms of audio
- **AND** the system SHALL detect when audio level falls below threshold
- **AND** the system SHALL stop recording after 1 second of continuous silence

#### Scenario: Streaming uses audio callback

- **WHEN** streaming audio
- **THEN** the system SHALL use a sounddevice audio callback
- **AND** the callback SHALL run in a separate thread
- **AND** the callback SHALL communicate with the async event loop via `asyncio.run_coroutine_threadsafe()`

#### Scenario: Streaming cleans up resources

- **GIVEN** an active streaming recording
- **WHEN** the recording stops (silence detected or iteration exhausted)
- **THEN** the system SHALL stop and close the audio stream
- **AND** the system SHALL clean up the audio device

---

### Requirement: AudioPlayer device enumeration

The system SHALL provide an `AudioPlayer` class for playing audio through speakers.

#### Scenario: Listing available output devices

- **WHEN** calling `AudioPlayer.list_devices()`
- **THEN** the system SHALL return a list of dictionaries
- **AND** each device dictionary SHALL contain:
  - `index: int` - device index
  - `name: str` - device name
  - `channels: int` - maximum output channels
  - `sample_rate: int` - default sample rate

#### Scenario: Only output devices are listed

- **WHEN** listing devices
- **THEN** devices SHALL be filtered to only include those with `max_output_channels > 0`

---

### Requirement: AudioPlayer initialization

The system SHALL allow creating an `AudioPlayer` with configurable parameters.

#### Scenario: Creating player with default parameters

- **WHEN** creating an `AudioPlayer` with no parameters
- **THEN** the following defaults SHALL be used:
  - `sample_rate: 24000` Hz
  - `channels: 1` (mono)
  - `device: None` (system default)

#### Scenario: Creating player with custom parameters

- **WHEN** creating an `AudioPlayer(sample_rate=16000, channels=2, device=5)`
- **THEN** the player SHALL use the specified parameters

---

### Requirement: Blocking audio playback

The system SHALL provide a `play()` method for playing audio and waiting for completion.

#### Scenario: Playing bytes audio

- **GIVEN** an initialized `AudioPlayer`
- **WHEN** calling `play(audio_bytes)` where `audio_bytes` is `bytes`
- **THEN** the system SHALL convert bytes to numpy array (dtype `int16`)
- **AND** the system SHALL play the audio through the output device
- **AND** the system SHALL block until playback is complete

#### Scenario: Playing numpy array audio

- **GIVEN** an initialized `AudioPlayer`
- **WHEN** calling `play(audio_array)` where `audio_array` is `np.ndarray`
- **THEN** the system SHALL play the audio directly
- **AND** the system SHALL block until playback is complete

---

### Requirement: Async audio playback

The system SHALL provide a `play_async()` method for non-blocking audio playback.

#### Scenario: Async playback completes without blocking event loop

- **GIVEN** an initialized `AudioPlayer`
- **WHEN** calling `play_async(audio_bytes)`
- **THEN** the system SHALL start audio playback
- **AND** the method SHALL return immediately (not block)
- **AND** the system SHALL poll for playback completion using `asyncio.sleep()`
- **AND** when a callback is provided, the system SHALL invoke it after playback completes

---

### Requirement: Streaming audio playback

The system SHALL provide a `play_stream()` method for low-latency streaming playback.

#### Scenario: Streaming plays chunks as they arrive

- **GIVEN** an initialized `AudioPlayer`
- **WHEN** calling `play_stream(audio_stream, pre_buffer_chunks=3)`
- **THEN** the system SHALL create a buffered queue
- **AND** the system SHALL run a producer task to receive chunks from the stream
- **AND** the system SHALL run a consumer task to play chunks
- **AND** the system SHALL buffer up to 3 chunks before starting playback
- **AND** the system SHALL play chunks as soon as they are available

#### Scenario: Streaming handles completion

- **WHEN** the audio stream ends (async iterator exhausted)
- **THEN** the producer task SHALL send a `None` signal to the queue
- **AND** the consumer task SHALL stop when receiving `None`

---

### Requirement: Playback control

The system SHALL provide a `stop()` method for stopping audio playback.

#### Scenario: Stop stops currently playing audio

- **GIVEN** audio is currently playing (via `play()` or `play_async()`)
- **WHEN** calling `stop()`
- **THEN** the system SHALL immediately stop audio playback

---

## Audio Format Reference

### Supported Audio Formats

| Parameter | Valid Values | Default |
|-----------|-------------|---------|
| Sample Rate | 16000, 24000 Hz | 24000 |
| Channels | 1 (mono) | 1 |
| Bit Depth | 16-bit (int16) | 16-bit |
| Data Type | numpy int16 array or bytes | - |

### Audio Chunk Sizes

| Duration (ms) | Bytes at 16kHz | Bytes at 24kHz |
|---------------|----------------|----------------|
| 80 ms | 2560 | 3840 |
| 100 ms | 3200 | 4800 |

### Silence Detection

Silence is detected using RMS (Root Mean Square) calculation:
- RMS < threshold → silent
- Default threshold: 0.01
- Adjusted via `silence_threshold` parameter
