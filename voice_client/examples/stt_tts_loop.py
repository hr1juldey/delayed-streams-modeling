#!/usr/bin/env python3
"""
STT to TTS Loop - Full speech-to-speech pipeline

This example demonstrates a complete voice processing loop:
1. Load audio file
2. Transcribe with STT
3. Generate agent response
4. Synthesize with TTS
5. Save output audio

Usage:
    python stt_tts_loop.py <input_audio.wav>

Output:
    Saves synthesized audio as <input_name>_response.wav in audio/
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice_client import AudioHandler, VoiceClient
from voice_client.exceptions import VoiceClientError


def simple_agent(transcription: str) -> str:
    """Simple agent that echoes and responds to the user.

    Args:
        transcription: The user's transcribed speech

    Returns:
        The agent's response text
    """
    transcription_lower = transcription.lower()

    if "hello" in transcription_lower or "hi" in transcription_lower:
        return "Hello! How can I help you today?"
    elif "how are you" in transcription_lower:
        return "I'm doing well, thank you for asking! How about you?"
    elif "bye" in transcription_lower or "goodbye" in transcription_lower:
        return "Goodbye! Have a great day!"
    elif "weather" in transcription_lower:
        return "I don't have access to weather information, but I hope it's nice outside!"
    elif "what is your name" in transcription_lower or "who are you" in transcription_lower:
        return "I'm a voice assistant powered by the voice server SDK."
    elif "thank" in transcription_lower:
        return "You're welcome! Is there anything else I can help with?"
    else:
        # Echo with acknowledgment
        return f"I heard you say: {transcription}"


async def main():
    """Run the STT to TTS loop."""
    # Check input file
    if len(sys.argv) < 2:
        print("Usage: python stt_tts_loop.py <input_audio.wav>")
        print("\nExample files in audio/:")
        audio_dir = Path(__file__).parent.parent.parent / "audio"
        for wav in audio_dir.glob("*.wav"):
            print(f"  {wav.name}")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    print("=" * 50)
    print("STT to TTS Loop")
    print("=" * 50)
    print(f"Input: {input_path}")
    print()

    # Determine output path
    output_dir = Path(__file__).parent.parent.parent / "audio"
    output_name = f"{input_path.stem}_response.wav"
    output_path = output_dir / output_name

    try:
        async with VoiceClient() as voice:
            # Step 1: Load and validate audio
            print("Step 1: Loading audio...")
            audio_bytes, sample_rate = AudioHandler.load_audio_file(input_path)
            AudioHandler.validate_audio(audio_bytes, sample_rate)
            print(f"  Loaded {len(audio_bytes)} bytes at {sample_rate} Hz")

            # Step 2: Transcribe
            print("\nStep 2: Transcribing with STT...")
            transcription, response_audio = await voice.converse(
                audio=audio_bytes,
                agent_callback=simple_agent,
            )
            print(f"  Transcription: \"{transcription}\"")

            # Get agent response (for display)
            response_text = simple_agent(transcription)
            print(f"  Response: \"{response_text}\"")

            # Step 3: Save synthesized audio
            print(f"\nStep 3: Saving audio to {output_path}...")
            AudioHandler.save_wav(response_audio, output_path, sample_rate=24000)
            print(f"  Saved {len(response_audio)} bytes")

            print("\n" + "=" * 50)
            print("Success!")
            print(f"Output saved to: {output_path}")
            print("=" * 50)

    except VoiceClientError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopped by user")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
