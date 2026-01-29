#!/bin/bash
# Production startup script for Voice Server

set -e

echo "Starting Voice Server (Production Mode)..."
echo ""

# Change to script directory
cd "$(dirname "$0")"
cd voice-server

# Create necessary directories
mkdir -p data/voices
mkdir -p data/db
mkdir -p logs

echo "Directories created/verified."
echo ""

# Load environment variables from .env if exists
if [ -f .env ]; then
    echo "Loading environment from .env..."
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set default environment variables
export VOICE_SERVER__HOST="${VOICE_SERVER__HOST:-0.0.0.0}"
export VOICE_SERVER__PORT="${VOICE_SERVER__PORT:-16000}"
export VOICE_SERVER__STT__PRELOAD_MODEL="${VOICE_SERVER_STT_PRELOAD_MODEL:-true}"
export VOICE_SERVER__TTS__PRELOAD_MODEL="${VOICE_SERVER_TTS_PRELOAD_MODEL:-true}"

echo "Configuration:"
echo "  Host: $VOICE_SERVER__HOST"
echo "  Port: $VOICE_SERVER__PORT"
echo "  STT Preload: $VOICE_SERVER__STT__PRELOAD_MODEL"
echo "  TTS Preload: $VOICE_SERVER__TTS__PRELOAD_MODEL"
echo ""

# Check GPU availability
if command -v nvidia-smi &> /dev/null; then
    echo "GPU detected:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv
    echo ""
else
    echo "No GPU detected (CPU mode)"
    echo ""
fi

# Check if required packages are installed
echo "Checking dependencies..."
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "  [ERROR] fastapi not found. Install with: pip install -e ."
    exit 1
fi

if ! python3 -c "import moshi" 2>/dev/null; then
    echo "  [WARNING] moshi (STT) not found. STT will not work."
fi

if ! python3 -c "import pocket_tts" 2>/dev/null; then
    echo "  [WARNING] pocket-tts not found. TTS will not work."
fi
echo ""

echo "Starting server..."
echo "  API docs: http://localhost:$VOICE_SERVER__PORT/docs"
echo "  Health: http://localhost:$VOICE_SERVER__PORT/health"
echo "  Metrics: http://localhost:$VOICE_SERVER__PORT/metrics"
echo ""

# Start server (no auto-reload in production)
python3 -m uvicorn src.main:app \
    --host "$VOICE_SERVER__HOST" \
    --port "$VOICE_SERVER__PORT" \
    --workers 1 \
    --log-level info \
    --access-log \
    --no-use-colors
