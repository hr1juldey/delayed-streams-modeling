"""Voice server test script.

Demonstrates STT and TTS functionality using audio files from the audio/ directory.
This script can be run from the voice_server/examples/ directory.
"""

import asyncio
import argparse
import subprocess
import sys
from pathlib import Path

# Audio files relative to this script (in voice_server/examples/)
AUDIO_FILES = {
    "bria": "../../audio/bria.mp3",
    "loona": "../../audio/loona.mp3",
    "hibiki": "../../audio/sample_fr_hibiki_crepes.mp3",
}

# TTS test texts
TTS_TESTS = [
    "Hello, this is a test of the text to speech system.",
    "The quick brown fox jumps over the lazy dog.",
    "Voice synthesis is working correctly.",
    "This is a longer sentence to test the streaming capabilities of the text to speech engine.",
    "Testing numbers: one, two, three, four, five.",
]


def run_stt_test(audio_name: str, url: str = "ws://localhost:16000/api/v1/ws/stt"):
    """Run STT test with specified audio file.

    Args:
        audio_name: Name of audio file (bria, loona, hibiki)
        url: WebSocket URL for STT endpoint.
    """
    if audio_name not in AUDIO_FILES:
        print(f"Error: Unknown audio file '{audio_name}'")
        print(f"Available: {', '.join(AUDIO_FILES.keys())}")
        return False

    audio_path = AUDIO_FILES[audio_name]
    full_path = Path(__file__).parent / audio_path

    if not full_path.exists():
        print(f"Error: Audio file not found: {full_path}")
        print(f"Please ensure audio files are in: {Path(__file__).parent.parent.parent / 'audio'}")
        return False

    print(f"\n{'='*60}")
    print(f"STT Test: {audio_name}")
    print(f"Audio file: {full_path}")
    print(f"{'='*60}\n")

    # Run stt_client.py
    cmd = [
        sys.executable,
        Path(__file__).parent / "stt_client.py",
        str(full_path),
        "--url", url,
    ]

    result = subprocess.run(cmd)
    return result.returncode == 0


def run_tts_test(text: str, output_file: str = None, url: str = "ws://localhost:16000/api/v1/ws/tts"):
    """Run TTS test with specified text.

    Args:
        text: Text to synthesize.
        output_file: Optional output file path.
        url: WebSocket URL for TTS endpoint.
    """
    print(f"\n{'='*60}")
    print(f"TTS Test")
    print(f"Text: \"{text}\"")
    print(f"{'='*60}\n")

    # Run tts_client.py
    cmd = [
        sys.executable,
        Path(__file__).parent / "tts_client.py",
        text,
        "--url", url,
    ]

    if output_file:
        cmd.extend(["--output", output_file])

    result = subprocess.run(cmd)
    return result.returncode == 0


def run_all_stt_tests(url: str = "ws://localhost:16000/api/v1/ws/stt"):
    """Run STT tests for all available audio files.

    Args:
        url: WebSocket URL for STT endpoint.
    """
    print("\n" + "="*60)
    print("Running ALL STT Tests")
    print("="*60)

    results = {}
    for name in AUDIO_FILES:
        results[name] = run_stt_test(name, url)

    print("\n" + "="*60)
    print("STT Test Results")
    print("="*60)
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")

    return all(results.values())


def run_all_tts_tests(url: str = "ws://localhost:16000/api/v1/ws/tts"):
    """Run TTS tests for all predefined texts.

    Args:
        url: WebSocket URL for TTS endpoint.
    """
    print("\n" + "="*60)
    print("Running ALL TTS Tests")
    print("="*60)

    results = {}
    for i, text in enumerate(TTS_TESTS, 1):
        output_file = Path(__file__).parent / f"output_{i}.wav"
        results[f"test_{i}"] = run_tts_test(text, str(output_file), url)

    print("\n" + "="*60)
    print("TTS Test Results")
    print("="*60)
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")

    return all(results.values())


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Voice Server Test Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all STT tests
  python run_tests.py --stt-all

  # Run STT test with specific audio file
  python run_tests.py --stt bria

  # Run TTS test with custom text
  python run_tests.py --tts "Hello world"

  # Run all tests
  python run_tests.py --all

  # Run with custom server URL
  python run_tests.py --all --url ws://192.168.1.4:16000/api/v1/ws/stt
        """
    )
    parser.add_argument(
        "--stt",
        choices=list(AUDIO_FILES.keys()),
        help="Run STT test with specific audio file",
    )
    parser.add_argument(
        "--stt-all",
        action="store_true",
        help="Run STT tests for all audio files",
    )
    parser.add_argument(
        "--tts",
        metavar="TEXT",
        help="Run TTS test with specified text",
    )
    parser.add_argument(
        "--tts-all",
        action="store_true",
        help="Run TTS tests for all predefined texts",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all STT and TTS tests",
    )
    parser.add_argument(
        "--url",
        default="ws://localhost:16000",
        help="Base WebSocket URL (default: ws://localhost:16000)",
    )
    parser.add_argument(
        "--stt-url",
        default="ws://localhost:16000/api/v1/ws/stt",
        help="STT WebSocket URL (overrides --url)",
    )
    parser.add_argument(
        "--tts-url",
        default="ws://localhost:16000/api/v1/ws/tts",
        help="TTS WebSocket URL (overrides --url)",
    )

    args = parser.parse_args()

    # Determine URLs
    stt_url = args.stt_url if args.stt_url != "ws://localhost:16000/api/v1/ws/stt" else args.url + "/api/v1/ws/stt"
    tts_url = args.tts_url if args.tts_url != "ws://localhost:16000/api/v1/ws/tts" else args.url + "/api/v1/ws/tts"

    # Track if any test was run
    tests_run = False
    all_passed = True

    # Run tests based on arguments
    if args.all:
        tests_run = True
        stt_passed = run_all_stt_tests(stt_url)
        tts_passed = run_all_tts_tests(tts_url)
        all_passed = stt_passed and tts_passed

    if args.stt_all and not args.all:
        tests_run = True
        all_passed = run_all_stt_tests(stt_url) and all_passed

    if args.stt:
        tests_run = True
        all_passed = run_stt_test(args.stt, stt_url) and all_passed

    if args.tts_all and not args.all:
        tests_run = True
        all_passed = run_all_tts_tests(tts_url) and all_passed

    if args.tts:
        tests_run = True
        all_passed = run_tts_test(args.tts, None, tts_url) and all_passed

    if not tests_run:
        parser.print_help()
        return 1

    # Print summary
    print("\n" + "="*60)
    if all_passed:
        print("✓ All tests PASSED")
    else:
        print("✗ Some tests FAILED")
    print("="*60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
