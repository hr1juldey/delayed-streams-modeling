"""Simple TTS test with more debugging and longer timeout."""

import asyncio
import base64
import json
import websockets


async def test_tts():
    url = "ws://localhost:16000/api/v1/ws/tts?encoding=json"

    async with websockets.connect(url) as ws:
        print("Connected!")

        # Configure
        config = {
            "type": "Config",
            "data": {
                "voice_id": "default",
                "output_format": "pcm_int16",
                "streaming": True,
            },
            "session_id": "test",
        }
        await ws.send(json.dumps(config))
        print("Config sent")

        # Get config ack
        response = await ws.recv()
        print(f"Config response: {response[:200]}")

        # Send shorter text
        text_msg = {
            "type": "Text",
            "data": "Hi",  # Very short text
            "session_id": "test",
        }
        await ws.send(json.dumps(text_msg))
        print("Text sent")

        # Receive audio chunks
        chunk_count = 0
        total_bytes = 0

        while True:
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=30.0)
                data = json.loads(response)

                if data.get("type") == "Audio":
                    audio_data = data.get("data", "")
                    chunk = base64.b64decode(audio_data)
                    chunk_count += 1
                    total_bytes += len(chunk)
                    print(f"Chunk {chunk_count}: {len(chunk)} bytes (total: {total_bytes})")

                elif data.get("type") == "Eos":
                    print(f"EOS received! Total: {chunk_count} chunks, {total_bytes} bytes")
                    break

                elif data.get("type") == "Error":
                    print(f"Error: {data.get('data')}")
                    break

                elif data.get("type") == "Config":
                    print(f"Config ack: {data}")

                else:
                    print(f"Unknown message type: {data.get('type')}")

            except asyncio.TimeoutError:
                print(f"Timeout after {chunk_count} chunks, {total_bytes} bytes")
                break


if __name__ == "__main__":
    asyncio.run(test_tts())
