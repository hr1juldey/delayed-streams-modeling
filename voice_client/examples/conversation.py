#!/usr/bin/env python3
"""
Conversation Example - Full duplex voice conversation

This example demonstrates how to use the voice client SDK
for a complete conversation: speech input -> STT -> Agent -> TTS -> speech output.

Requirements:
    - Voice server running on ws://localhost:16000/api/v1/ws
    - Audio file for input, or microphone for real-time input
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice_client import AudioPlayer, AudioRecorder, VoiceClient
from voice_client.exceptions import VoiceClientError


def simple_agent(transcription: str) -> str:
    """A simple echo agent that responds to the user.

    Args:
        transcription: The user's transcribed speech

    Returns:
        The agent's response text
    """
    # Simple responses based on keywords
    transcription_lower = transcription.lower()

    if "hello" in transcription_lower or "hi" in transcription_lower:
        return "Hello! How can I help you today?"
    elif "how are you" in transcription_lower:
        return "I'm doing well, thank you for asking! How about you?"
    elif "bye" in transcription_lower or "goodbye" in transcription_lower:
        return "Goodbye! Have a great day!"
    elif "weather" in transcription_lower:
        return "I don't have access to weather information, but I hope it's nice outside!"
    else:
        return f"You said: {transcription}"


async def main():
    """Run a voice conversation."""
    print("Voice Conversation Example")
    print("-" * 40)

    # Check if audio file provided
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        print(f"Using audio file: {audio_file}")
        use_mic = False
    else:
        print("Using microphone (speak after the prompt)")
        use_mic = True

    print()

    try:
        async with VoiceClient() as voice:
            # Get input audio
            if use_mic:
                print("Recording... (speak now)")
                recorder = AudioRecorder()

                audio_chunks = []
                async for chunk in recorder.record_stream(
                    chunk_size_ms=80,
                    silence_threshold=0.01,
                    silence_duration_ms=1500,
                ):
                    audio_chunks.append(chunk)
                    print(".", end="", flush=True)

                print()  # New line
                audio_input = b"".join(audio_chunks)
                print(f"Recorded {len(audio_input)} bytes")
            else:
                # Use file
                audio_input = audio_file

            # Run conversation
            print("\nProcessing...")
            transcription, response_audio = await voice.converse(
                audio=audio_input,
                agent_callback=simple_agent,
            )

            print(f"\nYou said: {transcription}")
            print(f"Response: {simple_agent(transcription)}")

            # Play response
            player = AudioPlayer()
            print("\nPlaying response...")
            player.play(response_audio)
            print("Done.")

    except VoiceClientError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopped by user")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
