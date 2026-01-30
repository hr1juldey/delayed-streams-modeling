#!/usr/bin/env python3
"""Debug test to trace WebSocket flow."""

import asyncio
import json
import base64
import numpy as np
import websockets


async def test():
    uri = "ws://localhost:16000/api/v1/ws/stt?api_key=test-key"
    print(f"Connecting to {uri}...")

    async with websockets.connect(uri, close_timeout=10) as ws:
        print("[1] Connected!")

        # Small delay to let server set up
        await asyncio.sleep(0.5)

        # Send config
        config = {"type": "config", "encoding": "json", "sample_rate": 24000}
        await ws.send(json.dumps(config))
        print("[2] Sent config")

        # Wait a bit
        await asyncio.sleep(0.5)

        # Check if we can receive anything
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
            print(f"[3] Received: {msg}")
        except asyncio.TimeoutError:
            print("[3] No message after config")

        # Send a small audio chunk
        audio = np.zeros(2400, dtype=np.float32)
        audio_msg = {
            "type": "audio",
            "data": base64.b64encode(audio.tobytes()).decode()
        }
        await ws.send(json.dumps(audio_msg))
        print("[4] Sent audio chunk")

        # Wait for response
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            print(f"[5] Received after audio: {msg}")
        except asyncio.TimeoutError:
            print("[5] Timeout after audio")

        # Send EOS
        await ws.send(json.dumps({"type": "eos"}))
        print("[6] Sent EOS")

        # Wait for final response
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
            print(f"[7] Received after EOS: {msg}")
        except asyncio.TimeoutError:
            print("[7] Timeout after EOS")

        print("[8] Keeping connection open for 2 seconds...")
        await asyncio.sleep(2)
        print("[9] Done")

    print("[10] Connection closed (context manager exit)")


if __name__ == "__main__":
    asyncio.run(test())
