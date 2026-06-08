#!/bin/bash
# Start Bump Detection System (API + Detection)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

source "$PROJECT_DIR/bump_env/bin/activate"

# Trap to clean up background API server on exit
cleanup() {
    echo ""
    echo "Stopping API server (PID: $API_PID)..."
    kill $API_PID 2>/dev/null
    wait $API_PID 2>/dev/null
    echo "Done."
}
trap cleanup EXIT INT TERM

echo "Starting API server..."
python "$SCRIPT_DIR/api_server.py" &
API_PID=$!
sleep 2

# Verify API server started
if kill -0 $API_PID 2>/dev/null; then
    echo "[OK] API server running (PID: $API_PID)"
else
    echo "[ERROR] API server failed to start!"
    exit 1
fi

echo "Starting bump detection..."
python "$SCRIPT_DIR/run_raspberry_pi.py"
