"""STT WebSocket client test script.

Demonstrates connecting to the STT WebSocket endpoint and
streaming audio for speech-to-text transcription.
"""

import asyncio
import argparse
import json
import time
import websockets
from pathlib import Path


async def test_stt_websocket(
    audio_file: str,
    url: str = "ws://localhost:16000/api/v1/ws/stt",
    api_key: str = None,
    encoding: str = "json",
):
    """Test the STT WebSocket endpoint.

    Args:
        audio_file: Path to audio file to transcribe.
        url: WebSocket URL.
        api_key: Optional API key for authentication.
        encoding: Message encoding (json or msgpack).
    """
    # Prepare URL with parameters
    ws_url = f"{url}?encoding={encoding}"
    if api_key:
        ws_url += f"&api_key={api_key}"

    print(f"Connecting to: {ws_url}")

    # Read audio file
    audio_path = Path(audio_file)
    if not audio_path.exists():
        print(f"Error: Audio file not found: {audio_file}")
        return

    with open(audio_path, "rb") as f:
        audio_data = f.read()

    print(f"Loaded audio: {len(audio_data)} bytes")

    try:
        async with websockets.connect(ws_url) as websocket:
            print("Connected!")

            # Send config message
            config = {
                "type": "Config",
                "data": {
                    "streaming_mode": "both",  # partial and final results
                    "input_format": "int16",
                },
                "session_id": "test-session",
            }
            await websocket.send(json.dumps(config))
            print("Sent config message")

            # Send audio in chunks
            chunk_size = 1920  # 80ms at 24kHz
            offset = 0
            chunk_count = 0

            while offset < len(audio_data):
                chunk = audio_data[offset:offset + chunk_size]

                # Create audio message
                message = {
                    "type": "Audio",
                    "data": chunk.hex() if encoding == "json" else chunk,
                    "session_id": "test-session",
                }

                # For JSON, we need to encode binary data as base64 or hex
                # The server expects raw bytes for MessagePack, but JSON needs encoding
                if encoding == "json":
                    # Convert hex back to bytes on server side
                    import base64
                    message["data"] = base64.b64encode(chunk).decode("ascii")

                await websocket.send(json.dumps(message))
                chunk_count += 1
                offset += chunk_size

                # Small delay between chunks to simulate real-time
                await asyncio.sleep(0.04)  # 40ms = 25 chunks per second

                # Receive and print any responses
                try:
                    response = await asyncio.wait_for(
                        websocket.recv(), timeout=0.01
                    )
                    await handle_response(response)
                except asyncio.TimeoutError:
                    pass

            print(f"Sent {chunk_count} audio chunks")

            # Send EOS
            eos_message = {
                "type": "Eos",
                "data": None,
                "session_id": "test-session",
            }
            await websocket.send(json.dumps(eos_message))
            print("Sent EOS")

            # Receive final responses
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    await handle_response(response)
                except asyncio.TimeoutError:
                    break

    except websockets.exceptions.WebSocketException as e:
        print(f"WebSocket error: {e}")
    except Exception as e:
        print(f"Error: {e}")


async def handle_response(response: str):
    """Handle a response from the server.

    Args:
        response: JSON response string.
    """
    try:
        data = json.loads(response)
        msg_type = data.get("type")

        if msg_type == "Text":
            text = data.get("data", "")
            is_partial = data.get("is_partial", False)
            is_final = data.get("is_final", False)
            confidence = data.get("confidence", 0.0)

            prefix = ""
            if is_partial:
                prefix = "[PARTIAL] "
            elif is_final:
                prefix = "[FINAL] "

            print(f"{prefix}\"{text}\" (confidence: {confidence:.2f})")

        elif msg_type == "Eos":
            print("[EOS] End of stream")

        elif msg_type == "Error":
            error = data.get("data", {})
            print(f"[ERROR] {error}")

        elif msg_type == "Config":
            print("[CONFIG] Configuration acknowledged")

    except json.JSONDecodeError:
        print(f"Invalid JSON response: {response}")


async def test_with_microphone(
    url: str = "ws://localhost:16000/api/v1/ws/stt",
    api_key: str = None,
    duration_seconds: int = 10,
):
    """Test STT with live microphone input.

    Args:
        url: WebSocket URL.
        api_key: Optional API key.
        duration_seconds: Recording duration.
    """
    print("Microphone test requires pyaudio.")
    print("Install with: pip install pyaudio")
    print("This is a placeholder - implement microphone capture if needed.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="STT WebSocket Test Client")
    parser.add_argument(
        "audio_file",
        nargs="?",
        help="Path to audio file (WAV, int16, 24kHz recommended)",
    )
    parser.add_argument(
        "--url",
        default="ws://localhost:16000/api/v1/ws/stt",
        help="WebSocket URL",
    )
    parser.add_argument(
        "--api-key",
        help="API key for authentication",
    )
    parser.add_argument(
        "--encoding",
        choices=["json", "msgpack"],
        default="json",
        help="Message encoding",
    )
    parser.add_argument(
        "--mic",
        action="store_true",
        help="Use microphone input",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Microphone recording duration (seconds)",
    )

    args = parser.parse_args()

    if args.mic:
        asyncio.run(test_with_microphone(args.url, args.api_key, args.duration))
    elif args.audio_file:
        asyncio.run(test_stt_websocket(args.audio_file, args.url, args.api_key, args.encoding))
    else:
        print("Please provide an audio file or use --mic for microphone input")
        parser.print_help()


if __name__ == "__main__":
    main()
