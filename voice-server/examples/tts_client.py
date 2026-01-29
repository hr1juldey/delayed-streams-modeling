"""TTS WebSocket client test script.

Demonstrates connecting to the TTS WebSocket endpoint and
receiving synthesized speech audio.
"""

import asyncio
import argparse
import base64
import io
import json
import wave
import websockets
from pathlib import Path


async def test_tts_websocket(
    text: str,
    output_file: str = None,
    url: str = "ws://localhost:16000/api/v1/ws/tts",
    api_key: str = None,
    encoding: str = "json",
    output_format: str = "pcm_int16",
    voice_id: str = "default",
):
    """Test the TTS WebSocket endpoint.

    Args:
        text: Text to synthesize.
        output_file: Optional output file path for audio.
        url: WebSocket URL.
        api_key: Optional API key for authentication.
        encoding: Message encoding (json or msgpack).
        output_format: Audio output format.
        voice_id: Voice ID to use.
    """
    # Prepare URL with parameters
    ws_url = f"{url}?encoding={encoding}"
    if api_key:
        ws_url += f"&api_key={api_key}"

    print(f"Connecting to: {ws_url}")
    print(f"Text: \"{text}\"")
    print(f"Voice: {voice_id}")
    print(f"Output format: {output_format}")

    audio_chunks = []

    try:
        async with websockets.connect(ws_url) as websocket:
            print("Connected!")

            # Send config message
            config = {
                "type": "Config",
                "data": {
                    "voice_id": voice_id,
                    "output_format": output_format,
                    "streaming": True,
                },
                "session_id": "test-session",
            }
            await websocket.send(json.dumps(config))
            print("Sent config message")

            # Send text message
            text_message = {
                "type": "Text",
                "data": text,
                "session_id": "test-session",
            }
            await websocket.send(json.dumps(text_message))
            print("Sent text message")

            # Receive audio chunks
            chunk_count = 0
            total_bytes = 0

            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)

                    data = json.loads(response)
                    msg_type = data.get("type")

                    if msg_type == "Audio":
                        # Extract audio data
                        audio_data = data.get("data", "")

                        if isinstance(audio_data, str):
                            # Base64 encoded
                            chunk = base64.b64decode(audio_data)
                        else:
                            # Should be bytes (for msgpack)
                            chunk = audio_data

                        audio_chunks.append(chunk)
                        chunk_count += 1
                        total_bytes += len(chunk)

                        print(f"Received chunk {chunk_count}: {len(chunk)} bytes")

                    elif msg_type == "Eos":
                        print("[EOS] End of synthesis")
                        break

                    elif msg_type == "Error":
                        error = data.get("data", {})
                        print(f"[ERROR] {error}")
                        break

                    elif msg_type == "Config":
                        print("[CONFIG] Configuration acknowledged")

                except asyncio.TimeoutError:
                    print("Timeout waiting for response")
                    break

            print(f"Received {chunk_count} chunks, {total_bytes} bytes total")

    except websockets.exceptions.WebSocketException as e:
        print(f"WebSocket error: {e}")
        return
    except Exception as e:
        print(f"Error: {e}")
        return

    # Save audio if output file specified
    if audio_chunks and output_file:
        save_audio(audio_chunks, output_file, output_format)


def save_audio(chunks: list[bytes], output_file: str, output_format: str):
    """Save audio chunks to file.

    Args:
        chunks: List of audio chunk bytes.
        output_file: Output file path.
        output_format: Audio format.
    """
    # Combine all chunks
    combined = b"".join(chunks)

    output_path = Path(output_file)

    if output_format == "wav" or output_file.endswith(".wav"):
        # For WAV format, the server should have sent WAV headers
        # If not, we need to create them
        if combined[:4] != b"RIFF":
            # Create WAV file manually
            with open(output_path, "wb") as f:
                # Write WAV header
                with wave.open(f, "wb") as wav:
                    wav.setnchannels(1)  # Mono
                    wav.setsampwidth(2)  # 16-bit = 2 bytes
                    wav.setframerate(24000)  # 24kHz
                    wav.writeframes(combined)
        else:
            # Already has WAV header
            with open(output_path, "wb") as f:
                f.write(combined)
    else:
        # Raw PCM
        with open(output_path, "wb") as f:
            f.write(combined)

    print(f"Saved audio to: {output_file} ({len(combined)} bytes)")


async def test_streaming_text(
    url: str = "ws://localhost:16000/api/v1/ws/tts",
    api_key: str = None,
):
    """Test streaming text synthesis (simulated real-time).

    Args:
        url: WebSocket URL.
        api_key: Optional API key.
    """
    ws_url = f"{url}?encoding=json"
    if api_key:
        ws_url += f"&api_key={api_key}"

    print("Testing streaming text synthesis...")

    try:
        async with websockets.connect(ws_url) as websocket:
            print("Connected!")

            # Send config
            config = {
                "type": "Config",
                "data": {
                    "voice_id": "default",
                    "output_format": "pcm_int16",
                    "streaming": True,
                },
                "session_id": "test-stream",
            }
            await websocket.send(json.dumps(config))

            # Simulate streaming text
            text_parts = [
                "Hello, ",
                "this is a ",
                "streaming ",
                "text synthesis ",
                "test.",
            ]

            audio_chunks = []

            for part in text_parts:
                print(f"Sending: \"{part}\"")

                text_message = {
                    "type": "Text",
                    "data": part,
                    "session_id": "test-stream",
                }
                await websocket.send(json.dumps(text_message))

                # Receive any audio chunks
                try:
                    while True:
                        response = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                        data = json.loads(response)

                        if data.get("type") == "Audio":
                            audio_data = data.get("data", "")
                            if isinstance(audio_data, str):
                                chunk = base64.b64decode(audio_data)
                            else:
                                chunk = audio_data
                            audio_chunks.append(chunk)
                            print(f"  Received audio: {len(chunk)} bytes")
                        else:
                            break
                except asyncio.TimeoutError:
                    pass

                # Small delay between parts
                await asyncio.sleep(0.5)

            # Send EOS
            eos_message = {
                "type": "Eos",
                "data": None,
                "session_id": "test-stream",
            }
            await websocket.send(json.dumps(eos_message))

            # Receive remaining audio
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(response)

                    if data.get("type") == "Audio":
                        audio_data = data.get("data", "")
                        if isinstance(audio_data, str):
                            chunk = base64.b64decode(audio_data)
                        else:
                            chunk = audio_data
                        audio_chunks.append(chunk)
                    elif data.get("type") == "Eos":
                        break
                except asyncio.TimeoutError:
                    break

            print(f"Total audio received: {sum(len(c) for c in audio_chunks)} bytes")

    except Exception as e:
        print(f"Error: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="TTS WebSocket Test Client")
    parser.add_argument(
        "text",
        nargs="?",
        help="Text to synthesize",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output audio file path",
    )
    parser.add_argument(
        "--url",
        default="ws://localhost:16000/api/v1/ws/tts",
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
        "--format",
        choices=["pcm_int16", "pcm_float32", "wav"],
        default="pcm_int16",
        help="Audio output format",
    )
    parser.add_argument(
        "--voice",
        default="default",
        help="Voice ID to use",
    )
    parser.add_argument(
        "--streaming-test",
        action="store_true",
        help="Run streaming text test",
    )

    args = parser.parse_args()

    if args.streaming_test:
        asyncio.run(test_streaming_text(args.url, args.api_key))
    elif args.text:
        asyncio.run(test_tts_websocket(
            args.text,
            args.output,
            args.url,
            args.api_key,
            args.encoding,
            args.format,
            args.voice,
        ))
    else:
        print("Please provide text to synthesize or use --streaming-test")
        parser.print_help()


if __name__ == "__main__":
    main()
