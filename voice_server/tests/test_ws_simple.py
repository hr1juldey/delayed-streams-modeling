#!/usr/bin/env python3
"""Simple WebSocket connection test."""

import asyncio
import websockets


async def test_stt():
    uri = "ws://localhost:16000/api/v1/ws/stt?api_key=test-key"
    print(f"Connecting to {uri}...")

    try:
        async with websockets.connect(uri, close_timeout=5) as ws:
            print("Connected!")

            # Wait for server message
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                print(f"Received: {msg}")
            except asyncio.TimeoutError:
                print("No message from server (timeout)")

            print("Connection still open, sleeping...")
            await asyncio.sleep(1)

            print("Closing...")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed: {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_stt())
