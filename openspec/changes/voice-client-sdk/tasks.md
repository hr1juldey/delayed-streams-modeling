# Voice Client SDK - Implementation Tasks

## 1. Package Structure and Dependencies

- [ ] 1.1 Create `voice_client/` package directory at project root (sibling to `voice_server/`)
- [ ] 1.2 Create `voice_client/__init__.py` with placeholder for exports
- [ ] 1.3 Update `requirements.txt` with new dependencies: `websockets>=14.0`, `sounddevice>=0.4.6`, `msgpack>=1.0.0`
- [ ] 1.4 Create `voice_client/examples/` directory for usage examples

## 2. Exception Hierarchy (exceptions.py)

- [ ] 2.1 Create `voice_client/exceptions.py` module
- [ ] 2.2 Implement base `VoiceClientError` exception class
- [ ] 2.3 Implement `ConnectionError` for WebSocket connection failures
- [ ] 2.4 Implement `AudioFormatError` for audio validation failures
- [ ] 2.5 Implement `ProtocolError` for message encoding/decoding errors
- [ ] 2.6 Implement `ConfigurationError` for invalid configuration
- [ ] 2.7 Implement `TimeoutError` for operation timeouts
- [ ] 2.8 Implement `ServerError` for server-reported errors
- [ ] 2.9 Implement `RecordingError` for audio recording failures
- [ ] 2.10 Implement `PlaybackError` for audio playback failures

## 3. WebSocket Protocol Layer (protocol.py)

- [ ] 3.1 Create `voice_client/protocol.py` module
- [ ] 3.2 Implement `MessageType` enum (AUDIO, TEXT, ERROR, EOS, CONFIG, HEARTBEAT)
- [ ] 3.3 Implement `Message` base dataclass with type, data, session_id, timestamp, metadata
- [ ] 3.4 Implement timestamp auto-generation in `Message.__post_init__`
- [ ] 3.5 Implement `AudioMessage` dataclass extending Message with audio-specific fields
- [ ] 3.6 Implement `TextMessage` dataclass extending Message with transcription fields
- [ ] 3.7 Implement `ErrorMessage` dataclass extending Message with error fields
- [ ] 3.8 Implement `EOSMessage` dataclass extending Message with reason field
- [ ] 3.9 Implement `ConfigMessage` dataclass extending Message with get_config method
- [ ] 3.10 Implement `JSONEncoder.encode()` with base64 encoding for audio data
- [ ] 3.11 Implement `JSONEncoder.decode()` with base64 decoding and type conversion
- [ ] 3.12 Implement `JSONEncoder._create_message()` factory for message type instantiation
- [ ] 3.13 Implement `MessagePackEncoder.encode()` with raw binary audio
- [ ] 3.14 Implement `MessagePackEncoder.decode()` with type conversion
- [ ] 3.15 Implement `MessagePackEncoder._create_message()` factory
- [ ] 3.16 Implement `get_encoder(encoding)` factory function
- [ ] 3.17 Implement convenience functions: `create_audio_message()`, `create_text_message()`, `create_config_message()`, `create_eos_message()`

## 4. Audio Handler (audio.py)

- [ ] 4.1 Create `voice_client/audio.py` module
- [ ] 4.2 Implement `AudioHandler` class with constants (sample rate, channels, bytes per sample, optimal chunk size)
- [ ] 4.3 Implement `AudioHandler.load_audio_file()` with auto-detection of format
- [ ] 4.4 Implement `AudioHandler._load_wav()` for WAV file parsing
- [ ] 4.5 Implement `AudioHandler._load_raw()` for raw PCM files
- [ ] 4.6 Add file existence validation in `load_audio_file()`
- [ ] 4.7 Add sample rate validation (16000 or 24000 Hz only)
- [ ] 4.8 Add channel count validation (mono only)
- [ ] 4.9 Add bit depth validation (16-bit only)
- [ ] 4.10 Implement `AudioHandler.calculate_chunk_size()` for target duration
- [ ] 4.11 Implement `AudioHandler.chunk_audio()` for splitting audio into chunks
- [ ] 4.12 Implement `AudioHandler.save_wav()` for writing WAV files

## 5. Audio I/O (audio_io.py)

- [ ] 5.1 Create `voice_client/audio_io.py` module
- [ ] 5.2 Implement `AudioRecorder` class with sample rate, channels, device configuration
- [ ] 5.3 Implement `AudioRecorder.list_devices()` for input devices
- [ ] 5.4 Implement `AudioRecorder.record()` for fixed-duration recording
- [ ] 5.5 Implement `AudioRecorder._trim_silence()` for silence removal
- [ ] 5.6 Implement `AudioRecorder.record_stream()` async generator with silence detection
- [ ] 5.7 Implement audio callback for streaming with thread-safe queue communication
- [ ] 5.8 Implement cleanup in `record_stream()` (stop and close stream)
- [ ] 5.9 Implement `AudioPlayer` class with sample rate, channels, device configuration
- [ ] 5.10 Implement `AudioPlayer.list_devices()` for output devices
- [ ] 5.11 Implement `AudioPlayer.play()` for blocking playback
- [ ] 5.12 Implement `AudioPlayer.play_async()` for non-blocking playback with polling
- [ ] 5.13 Implement `AudioPlayer.play_stream()` for buffered streaming playback
- [ ] 5.14 Implement producer/consumer pattern in `play_stream()` with pre-buffering
- [ ] 5.15 Implement `AudioPlayer.stop()` for stopping playback

## 6. Base Client (client.py)

- [ ] 6.1 Create `voice_client/client.py` module
- [ ] 6.2 Implement `BaseClient` class with URL, API key, encoding, timeout configuration
- [ ] 6.3 Implement URL construction with endpoint and query parameters
- [ ] 6.4 Implement `BaseClient.__aenter__()` for context manager entry
- [ ] 6.5 Implement `BaseClient.__aexit__()` for context manager exit
- [ ] 6.6 Implement `BaseClient.connect()` with exponential backoff reconnection
- [ ] 6.7 Implement reconnection delay calculation (1s initial, 30s max, exponential)
- [ ] 6.8 Implement `BaseClient.disconnect()` for graceful shutdown
- [ ] 6.9 Implement `BaseClient.send()` for message encoding and sending
- [ ] 6.10 Implement `BaseClient._message_loop()` background task for receiving messages
- [ ] 6.11 Implement message handler dispatch in `_message_loop()`
- [ ] 6.12 Implement `BaseClient.on_message()` for handler registration
- [ ] 6.13 Implement timeout handling in `_message_loop()`
- [ ] 6.14 Implement connection closed handling

## 7. STT Client (stt.py)

- [ ] 7.1 Create `voice_client/stt.py` module
- [ ] 7.2 Implement `STTClient` class extending `BaseClient`
- [ ] 7.3 Set `endpoint = "stt"` for WebSocket URL construction
- [ ] 7.4 Initialize default config (streaming_mode, input_format)
- [ ] 7.5 Initialize internal state (transcriptions list, final event)
- [ ] 7.6 Implement `STTClient.configure()` for sending ConfigMessage
- [ ] 7.7 Implement `STTClient.send_audio()` with file path or bytes support
- [ ] 7.8 Add audio format validation in `send_audio()`
- [ ] 7.9 Implement automatic chunking based on sample rate and chunk_size_ms
- [ ] 7.10 Implement audio chunk sending as AudioMessages
- [ ] 7.11 Implement `STTClient.send_eos()` for signaling end of stream
- [ ] 7.12 Implement `STTClient.get_transcription()` with timeout
- [ ] 7.13 Implement TEXT message handler for collecting transcriptions
- [ ] 7.14 Implement `STTClient.stream_transcription()` async generator
- [ ] 7.15 Implement `TranscriptionResult` dataclass (text, is_final, confidence)
- [ ] 7.16 Implement `STTClient.transcribe()` convenience method combining all steps

## 8. TTS Client (tts.py)

- [ ] 8.1 Create `voice_client/tts.py` module
- [ ] 8.2 Implement `TTSClient` class extending `BaseClient`
- [ ] 8.3 Set `endpoint = "tts"` for WebSocket URL construction
- [ ] 8.4 Initialize default config (voice_id, output_format, streaming)
- [ ] 8.5 Initialize internal state (audio queue, EOS event)
- [ ] 8.6 Implement `TTSClient.configure()` for sending ConfigMessage
- [ ] 8.7 Implement `TTSClient.synthesize()` async generator
- [ ] 8.8 Implement TEXT message sending for synthesis input
- [ ] 8.9 Implement AUDIO message handler for queueing audio chunks
- [ ] 8.10 Implement EOS message handler for stream completion
- [ ] 8.11 Implement ERROR message handler raising ServerError
- [ ] 8.12 Implement timeout handling in synthesis loop
- [ ] 8.13 Implement `AudioChunk` dataclass (data, format, sample_rate, is_final)
- [ ] 8.14 Implement `TTSClient.synthesize_full()` for collecting complete audio
- [ ] 8.15 Implement `TTSClient.synthesize_to_file()` for saving to WAV

## 9. Voice Client (voice.py)

- [ ] 9.1 Create `voice_client/voice.py` module
- [ ] 9.2 Implement `VoiceClient` class with STT and TTS client instances
- [ ] 9.3 Implement URL construction (separate URLs or shared base URL)
- [ ] 9.4 Implement `VoiceClient.__aenter__()` connecting both clients
- [ ] 9.5 Implement `VoiceClient.__aexit__()` disconnecting both clients
- [ ] 9.6 Implement partial connection failure handling
- [ ] 9.7 Implement `VoiceClient.converse()` for full conversation workflow
- [ ] 9.8 Implement agent callback invocation with transcription
- [ ] 9.9 Implement default echo response when no callback provided
- [ ] 9.10 Implement TTS synthesis of agent response
- [ ] 9.11 Implement returning tuple (transcription, response_audio)
- [ ] 9.12 Implement `VoiceClient.converse_stream()` async generator
- [ ] 9.13 Implement `ConversationEvent` dataclass (type, data, timestamp)
- [ ] 9.14 Implement event types: stt_partial, stt_final, tts_audio, complete
- [ ] 9.15 Expose `stt` and `tts` attributes for direct client access

## 10. Package Exports (__init__.py)

- [ ] 10.1 Update `voice_client/__init__.py` with exception exports
- [ ] 10.2 Export protocol classes (MessageType, all message types, encoders)
- [ ] 10.3 Export audio handler (AudioHandler)
- [ ] 10.4 Export audio I/O classes (AudioRecorder, AudioPlayer)
- [ ] 10.5 Export client classes (STTClient, TTSClient, VoiceClient)
- [ ] 10.6 Export dataclasses (TranscriptionResult, AudioChunk, ConversationEvent)
- [ ] 10.7 Export convenience functions (get_encoder, create_*_message functions)

## 11. Example Scripts

- [ ] 11.1 Create `examples/simple_stt.py` - Basic STT transcription from file
- [ ] 11.2 Create `examples/simple_tts.py` - Basic TTS synthesis to file
- [ ] 11.3 Create `examples/microphone_stt.py` - Real-time transcription from microphone
- [ ] 11.4 Create `examples/conversation.py` - Full conversation with agent callback
- [ ] 11.5 Add error handling and comments to all examples
- [ ] 11.6 Include usage instructions in each example file header

## 12. Testing

- [ ] 12.1 Test STT client with the running voice server
- [ ] 12.2 Test TTS client with the running voice server
- [ ] 12.3 Test full conversation workflow
- [ ] 12.4 Test audio file loading and validation
- [ ] 12.5 Test audio recording and playback (if hardware available)
- [ ] 12.6 Test error scenarios (invalid audio, connection failures, timeouts)
- [ ] 12.7 Test reconnection logic
- [ ] 12.8 Verify all examples run successfully

## 13. Documentation

- [ ] 13.1 Create `voice_client/README.md` with overview
- [ ] 13.2 Document installation instructions
- [ ] 13.3 Document quick start examples
- [ ] 13.4 Document API reference for all classes
- [ ] 13.5 Document audio format requirements
- [ ] 13.6 Document error handling best practices
- [ ] 13.7 Add troubleshooting section