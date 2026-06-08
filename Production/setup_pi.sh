#!/bin/bash
# ============================================================
# Raspberry Pi 5 Setup Script - Bump Detection Project
# Hardware: Pi 5 (8GB) + Pi Camera v2 + NEO-6M GPS
# ============================================================

set -e

echo "============================================================"
echo "  Bump Detection - Raspberry Pi 5 Setup"
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
    gpsd \
    gpsd-clients \
    python3-opencv \
    libcamera-apps \
    libatlas-base-dev \
    libhdf5-dev \
    libharfbuzz-dev \
    liblapack-dev \
    git
ok "System packages installed"

# ==================== 3. Enable Camera ====================
echo ""
echo "--- Step 3: Camera Setup ---"

# Check if camera is detected
if libcamera-hello --list-cameras 2>/dev/null | grep -q "Available"; then
    ok "Pi Camera detected"
else
    warn "Camera not detected. Make sure:"
    echo "      1. Camera ribbon cable is connected properly"
    echo "      2. Run: sudo raspi-config -> Interface -> Camera -> Enable"
    echo "      3. Reboot after enabling"
fi

# ==================== 4. GPS Setup (NEO-6M) ====================
echo ""
echo "--- Step 4: GPS Setup (NEO-6M) ---"

# Enable UART
if grep -q "enable_uart=1" /boot/firmware/config.txt 2>/dev/null; then
    ok "UART already enabled"
else
    echo "enable_uart=1" | sudo tee -a /boot/firmware/config.txt > /dev/null
    ok "UART enabled in config.txt"
fi

# Disable serial console (so GPS can use it)
sudo sed -i 's/console=serial0,115200 //g' /boot/firmware/cmdline.txt 2>/dev/null || true

# Configure gpsd
sudo tee /etc/default/gpsd > /dev/null << 'GPSDCONF'
START_DAEMON="true"
USBAUTO="true"
DEVICES="/dev/serial0"
GPSD_OPTIONS="-n"
GPSDCONF

sudo systemctl enable gpsd
sudo systemctl restart gpsd
ok "gpsd configured for /dev/serial0"

# ==================== 5. Python Environment ====================
echo ""
echo "--- Step 5: Python Virtual Environment ---"

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

if [ ! -d "bump_env" ]; then
    python3 -m venv bump_env --system-site-packages
    ok "Virtual environment created"
else
    ok "Virtual environment already exists"
fi

source bump_env/bin/activate

pip install --upgrade pip
pip install \
    ultralytics \
    opencv-python-headless \
    numpy \
    fastapi \
    uvicorn[standard] \
    pydantic \
    requests \
    gps
ok "Python packages installed"

# ==================== 6. Verify Setup ====================
echo ""
echo "--- Step 6: Verification ---"

# Check model file
MODEL_PATH="$PROJECT_DIR/runs/detect/train/weights/best.pt"
if [ -f "$MODEL_PATH" ]; then
    ok "YOLO model found ($(du -h "$MODEL_PATH" | cut -f1))"
else
    err "Model not found at: $MODEL_PATH"
    echo "      Copy it from your laptop:"
    echo "      scp runs/detect/train/weights/best.pt pi@<PI_IP>:~/BumpDetection/runs/detect/train/weights/"
fi

# Check camera device
if [ -e /dev/video0 ]; then
    ok "Camera device found (/dev/video0)"
else
    warn "No /dev/video0 - camera may need reboot after enabling"
fi

# Check GPS device
if [ -e /dev/serial0 ]; then
    ok "Serial device found (/dev/serial0)"
else
    warn "/dev/serial0 not found - check UART config and reboot"
fi

# Test GPS daemon
if systemctl is-active --quiet gpsd; then
    ok "gpsd is running"
else
    warn "gpsd is not running"
fi

# ==================== 7. Create startup script ====================
echo ""
echo "--- Step 7: Creating start script ---"

cat > "$PROJECT_DIR/Production/start.sh" << 'STARTSCRIPT'
#!/bin/bash
# Start Bump Detection System
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

source "$PROJECT_DIR/bump_env/bin/activate"

echo "Starting API server..."
python "$SCRIPT_DIR/api_server.py" &
API_PID=$!
sleep 2

echo "Starting bump detection..."
python "$SCRIPT_DIR/run_raspberry_pi.py"

# Cleanup
kill $API_PID 2>/dev/null
STARTSCRIPT

chmod +x "$PROJECT_DIR/Production/start.sh"
ok "Start script created: Production/start.sh"

# ==================== Done ====================
echo ""
echo "============================================================"
echo -e "  ${GREEN}SETUP COMPLETE!${NC}"
echo "============================================================"
echo ""
echo "  Wiring (NEO-6M GPS -> Pi 5):"
echo "    VCC -> Pin 1 (3.3V)"
echo "    GND -> Pin 6 (GND)"
echo "    TX  -> Pin 10 (GPIO15 / RXD)"
echo "    RX  -> Pin 8  (GPIO14 / TXD)"
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
echo "    libcamera-hello --timeout 3000"
echo ""
echo "  IMPORTANT: Reboot if this is the first time enabling"
echo "  UART or Camera!"
echo "    sudo reboot"
echo "============================================================"
