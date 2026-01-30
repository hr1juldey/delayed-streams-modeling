# Voice Client SDK

Python client SDK for the voice server with Speech-to-Text (STT) and Text-to-Speech (TTS) support via WebSocket.

## Features

- **Speech-to-Text (STT)**: Transcribe audio files or microphone input
- **Text-to-Speech (TTS)**: Synthesize speech from text
- **Full Conversations**: Combined STT + TTS pipeline
- **Audio I/O**: Microphone recording and speaker playback (optional)
- **Async/Await**: Modern async Python patterns
- **Auto-reconnection**: Exponential backoff on connection failures
- **Type-safe**: Full type hints and dataclasses
- **Preconfigured**: Sensible defaults, works out of the box

## Installation

```bash
pip install voice-client-sdk
```

With audio I/O support (microphone recording and speaker playback):
```bash
pip install voice-client-sdk[audio]
```

## Quick Start

### Speech-to-Text

```python
import asyncio
from voice_client import STTClient

async def main():
    async with STTClient() as stt:
        text = await stt.transcribe("speech.wav")
        print(f"Heard: {text}")

asyncio.run(main())
```

### Text-to-Speech

```python
import asyncio
from voice_client import TTSClient

async def main():
    async with TTSClient() as tts:
        audio = await tts.synthesize_full("Hello world!")
        # Save or play audio...

asyncio.run(main())
```

### Full Conversation

```python
import asyncio
from voice_client import VoiceClient

def agent_callback(transcription: str) -> str:
    return f"You said: {transcription}"

async def main():
    async with VoiceClient() as voice:
        transcription, response_audio = await voice.converse(
            "input.wav",
            agent_callback=agent_callback
        )
        print(f"User: {transcription}")

asyncio.run(main())
```

## Documentation

For more examples, see the `examples/` directory:

- `simple_stt.py` - Basic transcription from file
- `simple_tts.py` - Basic speech synthesis
- `microphone_stt.py` - Real-time microphone transcription
- `conversation.py` - Full duplex conversation
- `stt_tts_loop.py` - Complete STT → TTS pipeline

## Requirements

- Python 3.9+
- `websockets>=14.0`
- `msgpack>=1.0.0`

### Optional (for audio I/O)

- `sounddevice>=0.4.6`
- `numpy>=1.20.0`

## License

MIT License
