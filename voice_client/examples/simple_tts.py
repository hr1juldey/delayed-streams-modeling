#!/usr/bin/env python3
"""
Simple TTS Example - Synthesize speech from text

This example demonstrates how to use the voice client SDK
to synthesize speech from text.

Requirements:
    - Voice server running on ws://localhost:16000/api/v1/ws/tts
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice_client import TTSClient
from voice_client.exceptions import VoiceClientError


async def main():
    """Synthesize speech from text."""
    # Get text from command line or use default
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = "Hello, this is a test of the text to speech system."

    print(f"Synthesizing: {text}")
    print("-" * 40)

    try:
        async with TTSClient() as tts:
            # Get audio as bytes
            audio = await tts.synthesize_full(text)

            print(f"Generated {len(audio)} bytes of audio")

            # Optionally save to file
            output_path = "output.wav"
            await tts.synthesize_to_file(text, output_path)
            print(f"Saved to: {output_path}")

    except VoiceClientError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
