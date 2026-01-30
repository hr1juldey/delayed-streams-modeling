#!/usr/bin/env python3
"""Trace connection close timing."""

import asyncio
import json
import websockets


async def test():
    uri = "ws://localhost:16000/api/v1/ws/stt?api_key=test-key"
    print(f"Connecting to {uri}...")

    async with websockets.connect(uri, close_timeout=10) as ws:
        print("Connected!")

        # Wait 2 seconds
        print("Waiting 2 seconds before sending anything...")
        await asyncio.sleep(2)
        print("Still connected after 2 seconds")

        # Now send config
        print("Sending config...")
        config = {"type": "config", "encoding": "json", "sample_rate": 24000}
        await ws.send(json.dumps(config))
        print("Config sent!")

        # Try to receive immediately
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
            print(f"Received immediately after config: {msg}")
        except asyncio.TimeoutError:
            print("Timeout waiting for immediate response")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed right after sending config: {e}")
            return

        # Wait and try again
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            print(f"Received after waiting: {msg}")
        except asyncio.TimeoutError:
            print("Timeout waiting for response")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed: {e}")
            return

        print("Connection still open!")


if __name__ == "__main__":
    asyncio.run(test())
