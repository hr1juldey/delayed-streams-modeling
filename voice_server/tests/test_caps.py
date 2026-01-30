#!/usr/bin/env python3
"""Test with capitalized message types."""

import asyncio
import json
import websockets


async def test():
    uri = "ws://localhost:16000/api/v1/ws/stt?api_key=test-key"
    print(f"Connecting to {uri}...")

    async with websockets.connect(uri, close_timeout=10) as ws:
        print("Connected!")

        # Send config with CAPITALIZED type
        config = {"type": "Config", "encoding": "json", "sample_rate": 24000}
        await ws.send(json.dumps(config))
        print("Sent config with capitalized type")

        # Try to receive
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            print(f"Received: {msg}")
        except asyncio.TimeoutError:
            print("Timeout")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed: {e}")

        print("Done")


if __name__ == "__main__":
    asyncio.run(test())
