#!/usr/bin/env python3
"""
Microphone STT Example - Real-time speech transcription from microphone

This example demonstrates how to use the voice client SDK
to transcribe speech from microphone input.

Requirements:
    - Voice server running on ws://localhost:16000/api/v1/ws/stt
    - Microphone available on the system
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice_client import AudioRecorder, STTClient
from voice_client.exceptions import VoiceClientError


async def main():
    """Transcribe speech from microphone."""
    print("Microphone STT Example")
    print("-" * 40)
    print("Speak into your microphone...")
    print("(Recording will stop after silence)")
    print()

    # List available devices
    print("Available input devices:")
    devices = AudioRecorder.list_devices()
    for device in devices[:3]:  # Show first 3
        print(f"  [{device['index']}] {device['name']}")
    print()

    try:
        # Create recorder
        recorder = AudioRecorder()

        # Record audio with silence detection
        audio_chunks = []
        async for chunk in recorder.record_stream(
            chunk_size_ms=80,
            silence_threshold=0.01,
            silence_duration_ms=1000,
        ):
            audio_chunks.append(chunk)
            print(".", end="", flush=True)

        print()  # New line after dots

        # Combine chunks
        audio_bytes = b"".join(audio_chunks)
        print(f"Recorded {len(audio_bytes)} bytes")

        # Transcribe
        async with STTClient() as stt:
            print("Transcribing...")
            text = await stt.transcribe(audio_bytes)
            print(f"\nTranscription: {text}")

    except VoiceClientError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopped by user")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
