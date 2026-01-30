#!/usr/bin/env python3
"""
Simple STT Example - Transcribe audio from file

This example demonstrates how to use the voice client SDK
to transcribe speech from an audio file.

Requirements:
    - Voice server running on ws://localhost:16000/api/v1/ws/stt
    - Audio file in WAV format (16kHz or 24kHz, 16-bit, mono)
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice_client import STTClient
from voice_client.exceptions import VoiceClientError


async def main():
    """Transcribe an audio file."""
    # Configure the audio file path
    audio_file = sys.argv[1] if len(sys.argv) > 1 else "audio/bria.wav"

    print(f"Transcribing: {audio_file}")
    print("-" * 40)

    try:
        async with STTClient() as stt:
            # Send audio and get transcription
            text = await stt.transcribe(audio_file)

            print(f"Transcription: {text}")

    except VoiceClientError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
