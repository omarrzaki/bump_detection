# Bump Detection - Raspberry Pi 5 Setup Log

> هذا الملف يوثق كل الخطوات اللي اتعملت في إعداد الـ Raspberry Pi 5 للـ Bump Detection Project.
> آخر تحديث: قبل نقل المشروع للـ Pi.

---

## 📋 Project Overview

- **Project:** AI-powered speed bump detection for Egyptian roads
- **Model:** YOLOv8 (`runs/detect/train/weights/best.pt`)
- **Architecture:** Detection + FastAPI server on Pi → Flutter mobile app via REST
- **Reference:** See original `CLAUDE.md` for full architecture

---

## 🖥️ Hardware Inventory

| Component | Status | Notes |
|-----------|--------|-------|
| Raspberry Pi 5 | ✅ | 8GB model |
| SD Card | ✅ Flashed | Raspberry Pi OS Full 64-bit |
| Official 27W USB-C PSU | ✅ | Original Raspberry Pi |
| Pi Camera Module v2 (imx219) | ✅ Connected | Detected as `/base/axi/pcie@1000120000/rp1/i2c@88000/imx219@10` |
| u-blox NEO-6M GPS | ✅ Connected via USB | Module: `NEO-6M-0-001` (Serial: 24221843549) |
| Micro USB cable (for GPS) | ✅ | Data-capable cable |
| Micro HDMI to HDMI cable | ✅ | For local display |
| HP Monitor | ✅ | Connected via HDMI 0 |
| Wireless Mouse (Attack Shark X11) | ✅ | High DPI, working fine |
| USB Keyboard | ✅ | SINO WEALTH Gaming KB |
| Passive Heatsink (metal) | ✅ Installed | No fan — may need upgrade later |

---

## 🐧 Operating System

### Critical: NOT Bookworm — Using Trixie

```
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
NAME="Debian GNU/Linux"
VERSION_ID="13"
VERSION="13 (trixie)"
VERSION_CODENAME=trixie
DEBIAN_VERSION_FULL=13.4
```

### ⚠️ Important Differences from CLAUDE.md (which targets Bookworm)

| Old (Bookworm) | New (Trixie) |
|----------------|--------------|
| `libcamera-hello` | `rpicam-hello` |
| `pip install` works system-wide | **PEP 668 strict** — must use venv |
| Python 3.11 | Python 3.13 (likely) |

This affects:
- All `pip install` commands MUST be inside virtual environment
- Camera commands should use `rpicam-*` prefix (not `libcamera-*`)
- Some packages in `requirements.txt` may need version bumps

---

## 🔧 Imager Configuration (during SD card flash)

- **Device:** Raspberry Pi 5
- **OS:** Raspberry Pi OS Full (64-bit)
- **Hostname:** `raspberry` (default, can SSH as `raspberry.local`)
- **Username:** `pi`
- **Password:** [user-set, stored separately]
- **SSH:** ✅ Enabled with password authentication
- **Wi-Fi:** ✅ Configured (EG country code)
- **Locale:** Africa/Cairo, Arabic keyboard layout
- **Raspberry Pi Connect:** ❌ Disabled (not needed)

---

## 🌐 Network Configuration

- **IPs assigned:** `192.168.1.40`, `192.168.1.39`
  - One is WiFi, the other is Ethernet
  - Use `192.168.1.40` for SSH from laptop
- **Internet:** ✅ Working (`ping google.com` succeeds)
- **mDNS hostname:** `raspberry.local`

### SSH Command from laptop:
```bash
ssh [email protected]
# or
ssh [email protected]
```

---

## ⚙️ System Tweaks Applied

### 1. USB Current Limit Disabled
- **Path:** Raspberry Pi Configuration → Performance → "Disable USB Current Limit" toggle
- **Reason:** Default 600mA caused initial mouse lag concerns
- **Status:** ✅ Enabled (allows up to 1.6A on USB peripherals)
- **Safety:** OK with official 27W PSU

### 2. Mouse Lag Resolution
- **Root cause:** USB 3.0 EMI interference + low DPI on mouse
- **Initial issue:** Wireless mouse lagging when plugged into blue (USB 3.0) port
- **Fix attempted:** Move to USB 2.0 (black port) — didn't fully resolve
- **Final fix:** User increased DPI from button on mouse (Attack Shark X11)
- **Status:** ✅ Working at full speed now

### 3. Keyboard Layout
- **Initial state:** Arabic-only (set during Imager)
- **Updated:** Added English layout from Preferences
- **Status:** ✅ Both layouts available

---

## 📷 Camera Verification

```bash
rpicam-hello --list-cameras
```

**Output:**
```
Available cameras
-----------------
0 : imx219 [3280x2464 10-bit RGGB] (/base/axi/pcie@1000120000/rp1/i2c@88000/imx219@10)
    Modes: 'SRGGB10_CSI2P' : 640x480 [206.65 fps - (1000, 752)/1280x960 crop]
                             1640x1232 [41.85 fps - (0, 0)/3280x2464 crop]
                             1920x1080 [47.57 fps - (680, 692)/1920x1080 crop]
                             3280x2464 [21.19 fps - (0, 0)/3280x2464 crop]
           'SRGGB8' : 640x480 [206.65 fps - (1000, 752)/1280x960 crop]
                      1640x1232 [83.70 fps - (0, 0)/3280x2464 crop]
                      1920x1080 [47.57 fps - (680, 692)/1920x1080 crop]
                      3280x2464 [21.19 fps - (0, 0)/3280x2464 crop]
```

✅ Camera detected and functional. `imx219` chip confirms Pi Camera Module v2.

**Test command (live preview):**
```bash
rpicam-hello -t 10000
```

---

## 🛰️ GPS Setup

### Hardware
- **Module:** u-blox NEO-6M-0-001 (NOT NEO-8M as originally guessed from photos)
- **Connection:** Via Micro USB (NOT via GPIO/UART as in original CLAUDE.md)
- **Has integrated patch antenna** (no external antenna needed)

### Key Decision: USB instead of GPIO
- Original CLAUDE.md specified GPIO wiring (VCC, GND, TX, RX to pins 1, 6, 10, 8)
- User had no soldering equipment
- Module came with Micro USB port → switched to USB for simplicity
- **No soldering required** — yellow header pins came unsoldered but not needed

### USB Recognition
```bash
lsusb
```

**Output (relevant line):**
```
Bus 003 Device 004: ID 1546:01a6 U-Blox AG [u-blox 6]
```

✅ Module recognized by kernel.

### Critical: Device Path is `/dev/ttyACM0` NOT `/dev/ttyUSB0`
```bash
ls /dev/ttyACM*
# Output: /dev/ttyACM0
```

This is because u-blox modules use CDC-ACM driver, not USB-serial.

**⚠️ Code change required:**
In `run_raspberry_pi.py`, the device path needs:
```python
# Original (GPIO):
DEVICE = "/dev/ttyAMA0"  # or /dev/serial0

# Current (USB):
DEVICE = "/dev/ttyACM0"
```

### gpsd Installation
```bash
sudo apt update
sudo apt install -y gpsd gpsd-clients
```

### gpsd Configuration
File: `/etc/default/gpsd`
```
START_DAEMON="true"
GPSD_OPTIONS=""
DEVICES="/dev/ttyACM0"
USBAUTO="true"
GPSD_SOCKET="/var/run/gpsd.sock"
```

### Service Enabled
```bash
sudo systemctl restart gpsd
sudo systemctl enable gpsd
```

**Status:** ✅ Service enabled and running. Symlink created at:
`/etc/systemd/system/multi-user.target.wants/gpsd.service` → `/usr/lib/systemd/system/gpsd.service`

### GPS Fix Status
- **`cgps -s` was tested but user exited before confirming a fix**
- **Pending:** Need to verify GPS fix outdoors (or near window) — first fix can take 30s–5min
- LED indicators on module:
  - Red blinking = searching
  - Red solid / Blue blinking = fix acquired

---

## 🌡️ Thermal Status

### Idle Reading (no load)
```bash
vcgencmd measure_temp && vcgencmd get_throttled && vcgencmd measure_clock arm
```

**Output:**
```
temp=59.3'C
throttled=0x0
frequency(0)=2400023808
```

| Metric | Value | Status |
|--------|-------|--------|
| Temperature | 59.3°C | ✅ Good (idle) |
| Throttling | 0x0 | ✅ None |
| CPU Frequency | 2.4 GHz | ✅ Full speed |

### ⚠️ Cooling Concern
- Currently using **passive heatsink only** (no fan)
- Pi 5 known to run hot under sustained load (YOLOv8 inference + camera)
- **Recommendation:** Consider upgrading to **Official Active Cooler** for production use
- **Action item:** Run stress test under actual project load to verify thermal headroom

### Thermal Thresholds (Pi 5)
| Temp | Status |
|------|--------|
| < 60°C | ✅ Ideal |
| 60–75°C | ✅ Normal under load |
| 75–80°C | ⚠️ Soft throttle begins |
| 80–85°C | 🟠 Significant throttling |
| > 85°C | 🔴 Hard throttle (50% speed) |
| > 90°C | 🚨 Shutdown protection |

### Monitor command (use during project runs):
```bash
watch -n 2 vcgencmd measure_temp
```

---

## 📂 Project Directory (planned)

```
/home/pi/BumpDetection/
├── Production/
│   ├── api_server.py
│   ├── run_raspberry_pi.py    # ⚠️ Needs DEVICE = "/dev/ttyACM0"
│   ├── setup_pi.sh             # ⚠️ May need updates for Trixie
│   └── start.sh
├── runs/
│   └── detect/
│       └── train/
│           └── weights/
│               └── best.pt    # YOLOv8 model (~6-20MB)
└── requirements.txt           # ⚠️ Versions may need bump for Python 3.13
```

### What NOT to copy from laptop:
- ❌ `.git/`
- ❌ `__pycache__/`
- ❌ `bump_env/` (will create fresh on Pi)
- ❌ `Train AI_Model function/` (training data not needed for inference)
- ❌ `TestServer/`, `LiveCameraWithAPI/` (laptop-only)

---

## ⏭️ Next Steps (in order)

1. **Upload `Production/` to GitHub** (user's chosen method)
2. **Clone repo on Pi:**
   ```bash
   cd ~
   git clone <repo-url> BumpDetection
   ```
3. **Create Python virtual environment** (REQUIRED in Trixie — PEP 668):
   ```bash
   cd ~/BumpDetection
   python3 -m venv bump_env
   source bump_env/bin/activate
   pip install -r requirements.txt
   ```
4. **Code modifications needed:**
   - `run_raspberry_pi.py`: Update `DEVICE = "/dev/ttyACM0"`
   - `setup_pi.sh`: Replace `libcamera-apps` with `rpicam-apps` if present
   - Verify `ultralytics`, `opencv-python-headless`, `picamera2` versions work on Python 3.13
5. **Verify GPS fix** (move near window, run `cgps -s`, wait for FIX)
6. **Test camera capture** in Python (not just `rpicam-hello`)
7. **Run full project** and monitor:
   - Thermal: `watch -n 2 vcgencmd measure_temp`
   - API: `curl http://localhost:8000/`
8. **Address thermal if needed** (active cooler if temps exceed 80°C)

---

## 🐛 Known Issues / Watchlist

1. **Trixie vs Bookworm compatibility** — some `requirements.txt` packages may need updates
2. **`picamera2` on Trixie** — verify it works with Python 3.13
3. **GPS fix not yet confirmed** — `cgps -s` was run but exited before verification
4. **Thermal under load** — passive cooling untested under YOLOv8 inference
5. **`/dev/ttyACM0` permission** — may need `pi` user added to `dialout` group:
   ```bash
   sudo usermod -a -G dialout pi
   # then logout/login
   ```

---

## 📞 Reference Commands

### Power management
```bash
sudo reboot              # restart
sudo shutdown -h now     # safe shutdown
```

### System info
```bash
cat /etc/os-release      # OS version
hostname -I              # IP addresses
vcgencmd measure_temp    # CPU temperature
vcgencmd get_throttled   # throttling status
free -h                  # memory
df -h                    # disk
```

### Camera
```bash
rpicam-hello --list-cameras    # list cameras
rpicam-hello -t 10000           # 10-sec preview
rpicam-still -o test.jpg        # capture image
```

### GPS
```bash
ls /dev/ttyACM*                          # confirm device
sudo systemctl status gpsd               # service status
cgps -s                                  # live GPS data
gpspipe -w -n 5                          # raw JSON output (5 records)
```

### SSH from laptop (Ubuntu)
```bash
ssh [email protected]

# File transfer
scp file.py [email protected]:~/BumpDetection/
scp -r folder/ [email protected]:~/
```

---

## 📝 Outstanding Code Changes for AI Agent

When the AI agent (Antigravity) takes over, these are the specific changes needed in the project code:

### 1. `Production/run_raspberry_pi.py`
```python
# CHANGE THIS:
DEVICE = "/dev/ttyAMA0"   # or "/dev/serial0"

# TO THIS:
DEVICE = "/dev/ttyACM0"   # USB-connected u-blox NEO-6M
```

### 2. `Production/setup_pi.sh`
Search for any references to:
- `libcamera-apps` → replace with `rpicam-apps`
- `libcamera-*` → replace with `rpicam-*`

Add the dialout group fix:
```bash
sudo usermod -a -G dialout $USER
```

### 3. `requirements.txt`
If using strict version pins, may need bumps for Python 3.13 compatibility:
- `ultralytics>=8.3.0`
- `opencv-python-headless>=4.10.0`
- `picamera2` (use system package, not pip)

### 4. New consideration: PEP 668
Trixie blocks `pip install` outside venv. The setup script MUST:
1. Create `bump_env` first
2. Activate it
3. Then install requirements

OR use `pip install --break-system-packages` (NOT recommended).

---

## ✅ Verified Working

- [x] OS boot from SD card
- [x] WiFi connection
- [x] SSH access (from same network)
- [x] Camera detection (imx219)
- [x] GPS USB recognition (u-blox 6, `/dev/ttyACM0`)
- [x] gpsd service running
- [x] Mouse + keyboard
- [x] HDMI display output
- [x] Thermal in idle (59°C, no throttling)

## ⏳ Pending Verification

- [ ] Camera capture in Python (`picamera2` library)
- [ ] GPS fix acquired (need to verify outdoors)
- [ ] YOLOv8 inference performance
- [ ] Thermal under sustained load
- [ ] FastAPI server functional
- [ ] Mobile app (Flutter) connection
