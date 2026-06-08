#!/bin/bash
# Start Bump Detection System (API + Detection)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

source "$PROJECT_DIR/bump_env/bin/activate"

echo "Starting API server..."
python "$SCRIPT_DIR/api_server.py" &
API_PID=$!
sleep 2

echo "Starting bump detection..."
python "$SCRIPT_DIR/run_raspberry_pi.py"

# Cleanup on exit
kill $API_PID 2>/dev/null
