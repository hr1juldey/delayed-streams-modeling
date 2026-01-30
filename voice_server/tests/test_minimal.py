#!/usr/bin/env python3
"""Test with minimal config."""

import asyncio
import json
import websockets


async def test():
    uri = "ws://localhost:16000/api/v1/ws/stt"
    print(f"Connecting to {uri}...")

    async with websockets.connect(uri, close_timeout=10) as ws:
        print("Connected!")

        # Minimal config - no api_key since require_auth should be false
        config = {"type": "Config"}
        await ws.send(json.dumps(config))
        print("Sent minimal config")

        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            print(f"Received: {msg}")
        except asyncio.TimeoutError:
            print("Timeout")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed: {e}")


if __name__ == "__main__":
    asyncio.run(test())
