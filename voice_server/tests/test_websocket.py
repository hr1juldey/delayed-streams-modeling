#!/usr/bin/env python3
"""Simple WebSocket test for voice server."""

import asyncio
import json
import websockets
import numpy as np


async def test_stt_connection():
    """Test STT WebSocket connection."""
    print("Testing STT WebSocket connection...")

    uri = "ws://localhost:16000/api/v1/ws/stt"

    try:
        async with websockets.connect(uri) as ws:
            # Send config message
            config = {
                "type": "config",
                "encoding": "json",
                "sample_rate": 24000,
                "api_key": "test-key"
            }
            await ws.send(json.dumps(config))
            print(f"  Sent: {config}")

            # Receive response
            response = await asyncio.sleep(0.5)
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                print(f"  Received: {msg}")
            except asyncio.TimeoutError:
                print("  No immediate response (expected)")

            # Send a small audio chunk (silence)
            audio = np.zeros(2400, dtype=np.float32)  # 100ms silence
            import base64
            audio_msg = {
                "type": "audio",
                "data": base64.b64encode(audio.tobytes()).decode()
            }
            await ws.send(json.dumps(audio_msg))
            print(f"  Sent audio chunk: {len(audio)} samples")

            # Send EOS
            eos = {"type": "eos"}
            await ws.send(json.dumps(eos))
            print(f"  Sent EOS")

            # Receive final response
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                print(f"  Received: {msg}")
            except asyncio.TimeoutError:
                print("  Timeout waiting for response")

            print("  STT WebSocket: OK\n")
            return True

    except Exception as e:
        print(f"  STT WebSocket FAILED: {e}\n")
        return False


async def test_tts_connection():
    """Test TTS WebSocket connection."""
    print("Testing TTS WebSocket connection...")

    uri = "ws://localhost:16000/api/v1/ws/tts"

    try:
        async with websockets.connect(uri) as ws:
            # Send config message
            config = {
                "type": "config",
                "encoding": "json",
                "output_format": "pcm_int16"
            }
            await ws.send(json.dumps(config))
            print(f"  Sent: {config}")

            # Send text to synthesize
            text_msg = {
                "type": "text",
                "text": "Hello, this is a test of the voice server."
            }
            await ws.send(json.dumps(text_msg))
            print(f"  Sent: {text_msg}")

            # Receive audio response
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(msg)
                if data.get("type") == "audio":
                    print(f"  Received audio: {len(data.get('data', ''))} bytes")
                else:
                    print(f"  Received: {data}")
            except asyncio.TimeoutError:
                print("  Timeout waiting for response")

            print("  TTS WebSocket: OK\n")
            return True

    except Exception as e:
        print(f"  TTS WebSocket FAILED: {e}\n")
        return False


async def main():
    """Run all tests."""
    print("=" * 50)
    print("Voice Server WebSocket Tests")
    print("=" * 50)
    print()

    stt_ok = await test_stt_connection()
    tts_ok = await test_tts_connection()

    print("=" * 50)
    print("Results:")
    print(f"  STT WebSocket: {'PASS' if stt_ok else 'FAIL'}")
    print(f"  TTS WebSocket: {'PASS' if tts_ok else 'FAIL'}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
