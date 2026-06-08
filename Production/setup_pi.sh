#!/bin/bash
# ============================================================
# Raspberry Pi 5 Setup Script - Bump Detection Project
# ============================================================
# Hardware: Pi 5 (8GB) + Pi Camera v2 + NEO-6M GPS (USB)
# OS:       Debian 13 (Trixie) — NOT Bookworm!
# GPS:      Connected via USB (NOT GPIO/UART)
# ============================================================

set -e

echo "============================================================"
echo "  Bump Detection - Raspberry Pi 5 Setup"
echo "  OS: Trixie (Debian 13) | GPS: USB (/dev/ttyACM0)"
echo "============================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok() { echo -e "${GREEN}[OK]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# ==================== 1. System Update ====================
echo ""
echo "--- Step 1: System Update ---"
sudo apt update && sudo apt upgrade -y
ok "System updated"

# ==================== 2. Install Dependencies ====================
echo ""
echo "--- Step 2: Installing system packages ---"
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-gps \
    python3-picamera2 \
    gpsd \
    gpsd-clients \
    python3-opencv \
    rpicam-apps \
    libopenblas-dev \
    libhdf5-dev \
    libharfbuzz-dev \
    liblapack-dev \
    git
ok "System packages installed"

# ==================== 3. User Permissions ====================
echo ""
echo "--- Step 3: User Permissions ---"

# Add user to dialout group (required for GPS USB access)
if groups "$USER" | grep -q dialout; then
    ok "User '$USER' already in dialout group"
else
    sudo usermod -a -G dialout "$USER"
    ok "Added '$USER' to dialout group (logout/login needed to take effect)"
fi

# ==================== 4. Enable Camera ====================
echo ""
echo "--- Step 4: Camera Setup ---"

# Check if camera is detected (using rpicam for Trixie)
if rpicam-hello --list-cameras 2>/dev/null | grep -q "Available"; then
    ok "Pi Camera detected"
else
    warn "Camera not detected. Make sure:"
    echo "      1. Camera ribbon cable is connected properly"
    echo "      2. Run: sudo raspi-config -> Interface -> Camera -> Enable"
    echo "      3. Reboot after enabling"
fi

# ==================== 5. GPS Setup (NEO-6M via USB) ====================
echo ""
echo "--- Step 5: GPS Setup (NEO-6M via USB) ---"

# NOTE: GPS is connected via USB, NOT GPIO.
# No UART config needed. No soldering needed.
# The u-blox NEO-6M appears as /dev/ttyACM0 via CDC-ACM driver.

# Configure gpsd for USB GPS
sudo tee /etc/default/gpsd > /dev/null << 'GPSDCONF'
START_DAEMON="true"
USBAUTO="true"
DEVICES="/dev/ttyACM0"
GPSD_OPTIONS="-n"
GPSD_SOCKET="/var/run/gpsd.sock"
GPSDCONF

sudo systemctl enable gpsd
sudo systemctl restart gpsd
ok "gpsd configured for /dev/ttyACM0 (USB GPS)"

# ==================== 6. Python Environment ====================
echo ""
echo "--- Step 6: Python Virtual Environment ---"
echo "  (PEP 668 on Trixie requires venv for pip installs)"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

if [ ! -d "bump_env" ]; then
    python3 -m venv bump_env --system-site-packages
    ok "Virtual environment created (with system-site-packages)"
else
    ok "Virtual environment already exists"
fi

source bump_env/bin/activate

pip install --upgrade pip

# Install from requirements.txt if available
if [ -f "Production/requirements.txt" ]; then
    pip install -r Production/requirements.txt
    ok "Python packages installed from requirements.txt"
else
    warn "No requirements.txt found, installing packages manually"
    pip install \
        ultralytics \
        opencv-python-headless \
        numpy \
        fastapi \
        "uvicorn[standard]" \
        pydantic \
        requests \
        gps
    ok "Python packages installed"
fi

# ==================== 7. Verify Setup ====================
echo ""
echo "--- Step 7: Verification ---"

# Check model file
MODEL_PATH="$SCRIPT_DIR/best.pt"
if [ -f "$MODEL_PATH" ]; then
    ok "YOLO model found: $(du -h "$MODEL_PATH" | cut -f1)"
else
    err "Model not found at: $MODEL_PATH"
    echo "      Make sure best.pt is in the Production/ folder"
fi

# Check camera device
if [ -e /dev/video0 ]; then
    ok "Camera device found (/dev/video0)"
else
    warn "No /dev/video0 - camera may need reboot after enabling"
fi

# Check GPS USB device
if [ -e /dev/ttyACM0 ]; then
    ok "GPS USB device found (/dev/ttyACM0)"
else
    warn "/dev/ttyACM0 not found - is the GPS module plugged in via USB?"
fi

# Test GPS daemon
if systemctl is-active --quiet gpsd; then
    ok "gpsd is running"
else
    warn "gpsd is not running"
fi

# Python import tests
echo ""
echo "--- Quick Python Import Tests ---"
source "$PROJECT_DIR/bump_env/bin/activate"

python3 -c "import ultralytics; print('[OK] ultralytics', ultralytics.__version__)" 2>/dev/null || warn "ultralytics import failed"
python3 -c "import cv2; print('[OK] opencv', cv2.__version__)" 2>/dev/null || warn "opencv import failed"
python3 -c "import fastapi; print('[OK] fastapi', fastapi.__version__)" 2>/dev/null || warn "fastapi import failed"
python3 -c "import numpy; print('[OK] numpy', numpy.__version__)" 2>/dev/null || warn "numpy import failed"

# ==================== 8. Create startup script ====================
echo ""
echo "--- Step 8: Creating start script ---"

cat > "$SCRIPT_DIR/start.sh" << 'STARTSCRIPT'
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
STARTSCRIPT

chmod +x "$SCRIPT_DIR/start.sh"
ok "Start script created: Production/start.sh"

# ==================== Done ====================
echo ""
echo "============================================================"
echo -e "  ${GREEN}SETUP COMPLETE!${NC}"
echo "============================================================"
echo ""
echo "  Hardware Summary:"
echo "    Camera: Pi Camera Module v2 (imx219) — ribbon cable"
echo "    GPS:    NEO-6M via USB (/dev/ttyACM0) — no soldering"
echo ""
echo "  To run:"
echo "    cd $PROJECT_DIR"
echo "    source bump_env/bin/activate"
echo "    cd Production"
echo "    ./start.sh"
echo ""
echo "  Or manually:"
echo "    python Production/api_server.py    (Terminal 1)"
echo "    python Production/run_raspberry_pi.py  (Terminal 2)"
echo ""
echo "  Test GPS:"
echo "    cgps -s"
echo ""
echo "  Test Camera:"
echo "    rpicam-hello --timeout 3000"
echo ""
echo "  Monitor Temperature:"
echo "    watch -n 2 vcgencmd measure_temp"
echo ""
if ! groups "$USER" | grep -q dialout; then
    echo -e "  ${YELLOW}⚠ IMPORTANT: Logout and login again for dialout"
    echo -e "  group to take effect (needed for GPS access)!${NC}"
    echo ""
fi
echo "============================================================"
