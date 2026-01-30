#!/usr/bin/env python3
"""Test STT WebSocket with actual audio."""

import asyncio
import json
import base64
import numpy as np
import websockets


async def test_stt_with_audio():
    uri = "ws://localhost:16000/api/v1/ws/stt?api_key=test-key"
    print(f"Connecting to {uri}...")

    try:
        async with websockets.connect(uri, close_timeout=10) as ws:
            print("Connected!")

            # Send config
            config = {
                "type": "config",
                "encoding": "json",
                "sample_rate": 24000
            }
            await ws.send(json.dumps(config))
            print(f"Sent config")

            # Create 1 second of silence (24000 samples at 24kHz)
            audio = np.zeros(24000, dtype=np.float32)

            # Send in chunks
            chunk_size = 2400  # 100ms chunks
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i:i+chunk_size]
                audio_msg = {
                    "type": "audio",
                    "data": base64.b64encode(chunk.tobytes()).decode()
                }
                await ws.send(json.dumps(audio_msg))

            print(f"Sent {len(audio)} samples of audio")

            # Send EOS
            await ws.send(json.dumps({"type": "eos"}))
            print("Sent EOS")

            # Receive responses
            print("\nWaiting for responses...")
            for _ in range(10):  # Wait for up to 10 messages
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    data = json.loads(msg)
                    print(f"Received: type={data.get('type')}, text='{data.get('text', '')}'")

                    if data.get("type") == "eos":
                        print("Got EOS, done!")
                        break
                except asyncio.TimeoutError:
                    print("Timeout waiting for response")
                    break

    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed: {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_stt_with_audio())
