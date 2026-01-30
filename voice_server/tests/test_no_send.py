#!/usr/bin/env python3
"""Test just connecting without sending anything."""

import asyncio
import websockets


async def test():
    uri = "ws://localhost:16000/api/v1/ws/stt?api_key=test-key"
    print(f"Connecting to {uri}...")

    async with websockets.connect(uri, close_timeout=10) as ws:
        print("Connected!")

        # Just wait without sending anything
        print("Waiting 5 seconds without sending...")
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            print(f"Received: {msg}")
        except asyncio.TimeoutError:
            print("Timeout (expected - no message from server)")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed: {e}")

        print("Done")


if __name__ == "__main__":
    asyncio.run(test())
