#!/bin/bash
# Development startup script for Voice Server

set -e

echo "Starting Voice Server (Development Mode)..."
echo ""

# Change to voice-server directory
cd "$(dirname "$0")"
cd voice-server

# Create necessary directories
mkdir -p data/voices
mkdir -p data/db
mkdir -p logs

echo "Directories created/verified."
echo ""

# Set default environment variables if not set
export VOICE_SERVER__HOST="${VOICE_SERVER_HOST:-0.0.0.0}"
export VOICE_SERVER__PORT="${VOICE_SERVER_PORT:-16000}"
export VOICE_SERVER__STT__PRELOAD_MODEL="${VOICE_SERVER_STT_PRELOAD_MODEL:-false}"
export VOICE_SERVER__TTS__PRELOAD_MODEL="${VOICE_SERVER_TTS_PRELOAD_MODEL:-false}"

echo "Configuration:"
echo "  Host: $VOICE_SERVER__HOST"
echo "  Port: $VOICE_SERVER__PORT"
echo "  STT Preload: $VOICE_SERVER__STT__PRELOAD_MODEL"
echo "  TTS Preload: $VOICE_SERVER__TTS__PRELOAD_MODEL"
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"
echo ""

# Check if required packages are installed
echo "Checking dependencies..."
python3 -c "import fastapi" 2>/dev/null || echo "  [WARNING] fastapi not found"
python3 -c "import websockets" 2>/dev/null || echo "  [WARNING] websockets not found"
python3 -c "import moshi" 2>/dev/null || echo "  [WARNING] moshi (STT) not found"
python3 -c "import pocket_tts" 2>/dev/null || echo "  [WARNING] pocket-tts not found"
echo ""

echo "Starting server..."
echo "  API docs: http://localhost:16000/docs"
echo "  Health: http://localhost:16000/health"
echo "  Metrics: http://localhost:16000/metrics"
echo ""

# Start server with auto-reload
python3 -m uvicorn src.main:app \
    --host "$VOICE_SERVER__HOST" \
    --port "$VOICE_SERVER__PORT" \
    --reload \
    --log-level info
