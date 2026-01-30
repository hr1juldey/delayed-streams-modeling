"""Full conversation example demonstrating STT + TTS flow.

This example shows a complete voice interaction flow:
1. User speaks (audio input)
2. STT transcribes to text
3. Application processes text (e.g., sends to LLM)
4. TTS synthesizes response (audio output)
5. User hears response

This pattern can be used with any AI agent (DSPy + Ollama, etc.).
"""

import asyncio
import argparse
import base64
import json
import websockets
from pathlib import Path
from typing import AsyncIterator, Optional


class VoiceConversationClient:
    """Client for full-duplex voice conversation."""

    def __init__(
        self,
        stt_url: str = "ws://localhost:16000/api/v1/ws/stt",
        tts_url: str = "ws://localhost:16000/api/v1/ws/tts",
        api_key: Optional[str] = None,
    ):
        """Initialize the voice conversation client.

        Args:
            stt_url: STT WebSocket URL.
            tts_url: TTS WebSocket URL.
            api_key: Optional API key.
        """
        self.stt_url = f"{stt_url}?encoding=json"
        self.tts_url = f"{tts_url}?encoding=json"
        if api_key:
            self.stt_url += f"&api_key={api_key}"
            self.tts_url += f"&api_key={api_key}"

        self.stt_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.tts_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False

    async def connect(self):
        """Connect to both STT and TTS WebSocket endpoints."""
        print("Connecting to STT...")
        self.stt_ws = await websockets.connect(self.stt_url)
        print("STT connected!")

        print("Connecting to TTS...")
        self.tts_ws = await websockets.connect(self.tts_url)
        print("TTS connected!")

        # Configure STT
        await self.stt_ws.send(
            json.dumps({
                "type": "Config",
                "data": {
                    "streaming_mode": "both",
                    "input_format": "int16",
                },
                "session_id": "conversation",
            })
        )

        # Configure TTS
        await self.tts_ws.send(
            json.dumps({
                "type": "Config",
                "data": {
                    "voice_id": "default",
                    "output_format": "pcm_int16",
                    "streaming": True,
                },
                "session_id": "conversation",
            })
        )

        print("Configured both endpoints!")

    async def disconnect(self):
        """Disconnect from both endpoints."""
        self.running = False

        if self.stt_ws:
            await self.stt_ws.close()
        if self.tts_ws:
            await self.tts_ws.close()

        print("Disconnected!")

    async def process_conversation(
        self,
        audio_file: str,
        agent_response: str = None,
        save_output: str = None,
    ):
        """Process a full conversation turn.

        Args:
            audio_file: Input audio file (user speech).
            agent_response: Agent's text response (or use echo).
            save_output: Optional file to save TTS audio.
        """
        if not self.stt_ws or not self.tts_ws:
            raise RuntimeError("Not connected! Call connect() first.")

        self.running = True

        # Step 1: Send user audio to STT
        print("\n=== Step 1: Transcribing user speech ===")
        transcription = await self._transcribe_audio(audio_file)

        if not transcription:
            print("No transcription received!")
            return

        print(f'\nUser said: "{transcription}"')

        # Step 2: Process with agent (you can integrate your agent here)
        print("\n=== Step 2: Processing with agent ===")
        response_text = await self._process_with_agent(transcription, agent_response)
        print(f'Agent response: "{response_text}"')

        # Step 3: Synthesize agent response with TTS
        print("\n=== Step 3: Synthesizing agent response ===")
        await self._synthesize_speech(response_text, save_output)

        print("\n=== Conversation turn complete! ===")

    async def _transcribe_audio(self, audio_file: str) -> Optional[str]:
        """Transcribe audio file using STT.

        Args:
            audio_file: Path to audio file.

        Returns:
            Transcribed text, or None if failed.
        """
        audio_path = Path(audio_file)
        if not audio_path.exists():
            print(f"Error: Audio file not found: {audio_file}")
            return None

        with open(audio_path, "rb") as f:
            audio_data = f.read()

        print(f"Sending audio: {len(audio_data)} bytes")

        # Send audio in chunks
        chunk_size = 1920  # 80ms at 24kHz
        offset = 0
        final_text = ""

        while offset < len(audio_data):
            chunk = audio_data[offset : offset + chunk_size]

            message = {
                "type": "Audio",
                "data": base64.b64encode(chunk).decode("ascii"),
                "session_id": "conversation",
            }
            await self.stt_ws.send(json.dumps(message))

            offset += chunk_size

            # Check for responses
            response = await self._get_stt_response(timeout=0.01)
            if response:
                print(f"  [Partial] {response}")

        # Send EOS and get final result
        await self.stt_ws.send(
            json.dumps({
                "type": "Eos",
                "data": None,
                "session_id": "conversation",
            })
        )

        # Get final transcription
        while True:
            response = await self._get_stt_response(timeout=2.0)
            if response:
                final_text = response
                print(f"  [Final] {final_text}")
            else:
                break

        return final_text

    async def _get_stt_response(self, timeout: float = 0.1) -> Optional[str]:
        """Get response from STT endpoint.

        Args:
            timeout: Timeout in seconds.

        Returns:
            Transcribed text if available, None otherwise.
        """
        try:
            response = await asyncio.wait_for(self.stt_ws.recv(), timeout=timeout)
            data = json.loads(response)

            if data.get("type") == "Text":
                text = data.get("data", "")
                if data.get("is_final"):
                    return text
                return None  # Skip partial results

            return None

        except asyncio.TimeoutError:
            return None

    async def _process_with_agent(self, user_text: str, agent_response: str = None) -> str:
        """Process user text with an agent.

        This is where you would integrate your AI agent (DSPy, Ollama, etc.).

        Args:
            user_text: User's transcribed speech.
            agent_response: Pre-defined response (for testing).

        Returns:
            Agent's response text.
        """
        if agent_response:
            return agent_response

        # Default: echo back (replace with your agent)
        return f"You said: {user_text}"

    async def _synthesize_speech(
        self,
        text: str,
        save_output: str = None,
    ):
        """Synthesize speech from text using TTS.

        Args:
            text: Text to synthesize.
            save_output: Optional file to save audio.
        """
        print(f'Synthesizing: "{text}"')

        # Send text to TTS
        await self.tts_ws.send(
            json.dumps({
                "type": "Text",
                "data": text,
                "session_id": "conversation",
            })
        )

        # Receive audio chunks
        audio_chunks = []
        chunk_count = 0

        while True:
            try:
                response = await asyncio.wait_for(self.tts_ws.recv(), timeout=5.0)
                data = json.loads(response)

                if data.get("type") == "Audio":
                    audio_data = data.get("data", "")
                    chunk = base64.b64decode(audio_data)
                    audio_chunks.append(chunk)
                    chunk_count += 1
                    print(f"  Received chunk {chunk_count}: {len(chunk)} bytes")

                elif data.get("type") == "Eos":
                    print("  Synthesis complete!")
                    break

            except asyncio.TimeoutError:
                print("  Timeout waiting for audio")
                break

        # Save audio if requested
        if audio_chunks and save_output:
            combined = b"".join(audio_chunks)
            with open(save_output, "wb") as f:
                f.write(combined)
            print(f"  Saved audio to: {save_output}")

    async def run_interactive(self):
        """Run interactive conversation mode.

        This mode would allow continuous conversation with the agent.
        Placeholder for future implementation.
        """
        print("Interactive mode not yet implemented.")
        print("Use process_conversation() for single-turn conversations.")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Full Voice Conversation Example")
    parser.add_argument(
        "audio_file",
        help="Input audio file (user speech)",
    )
    parser.add_argument(
        "--response",
        "-r",
        help="Agent response text (default: echo)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Save TTS audio to file",
    )
    parser.add_argument(
        "--stt-url",
        default="ws://localhost:16000/api/v1/ws/stt",
        help="STT WebSocket URL",
    )
    parser.add_argument(
        "--tts-url",
        default="ws://localhost:16000/api/v1/ws/tts",
        help="TTS WebSocket URL",
    )
    parser.add_argument(
        "--api-key",
        help="API key for authentication",
    )

    args = parser.parse_args()

    # Create client
    client = VoiceConversationClient(args.stt_url, args.tts_url, args.api_key)

    try:
        # Connect
        await client.connect()

        # Process conversation
        await client.process_conversation(
            args.audio_file,
            args.response,
            args.output,
        )

    finally:
        # Disconnect
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
