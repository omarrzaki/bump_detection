# Bump Detection - Raspberry Pi 5 Setup Log

> هذا الملف يوثق كل الخطوات اللي اتعملت في إعداد الـ Raspberry Pi 5 للـ Bump Detection Project.
> آخر تحديث: 2026-06-09 (بعد deployment وتشغيل أول session ناجحة)

---

## 📋 Project Overview

- **Project:** AI-powered speed bump detection for Egyptian roads
- **Model:** YOLOv8 (`Production/best.pt` — 6MB)
- **Architecture:** Detection + FastAPI server on Pi → Flutter mobile app via REST
- **API Version:** v3.0 (with spatial dedup, device tracking, min_confirmations)
- **Camera Backend:** `picamera2` (libcamera stack — required for Pi 5 Trixie)

---

## 🖥️ Hardware Inventory

| Component | Status | Notes |
|-----------|--------|-------|
| Raspberry Pi 5 | ✅ | 8GB model |
| SD Card | ✅ Flashed | Raspberry Pi OS Full 64-bit |
| Official 27W USB-C PSU | ✅ | Original Raspberry Pi |
| Pi Camera Module v2 (imx219) | ✅ Working in Python | Via picamera2, 640x480 confirmed |
| u-blox NEO-6M GPS | ✅ GPS Fix acquired | Module: `NEO-6M-0-001`, USB `/dev/ttyACM0` |
| Micro USB cable (for GPS) | ✅ | Data-capable cable |
| Micro HDMI to HDMI cable | ✅ | For local display |
| HP Monitor | ✅ | Connected via HDMI 0 |
| Wireless Mouse (Attack Shark X11) | ✅ | High DPI, working fine |
| USB Keyboard | ✅ | SINO WEALTH Gaming KB |
| Passive Heatsink (metal) | ✅ Installed | No fan — may need upgrade under sustained load |

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

### Trixie-specific adaptations (ALL DONE ✅)

| Issue | Old (Bookworm) | New (Trixie) | Status |
|-------|----------------|--------------|--------|
| Camera commands | `libcamera-*` | `rpicam-*` | ✅ Fixed |
| Camera in Python | `cv2.VideoCapture` (V4L2) | `picamera2` (libcamera) | ✅ Fixed |
| pip installs | System-wide | **PEP 668** — venv only | ✅ Fixed |
| Python version | 3.11 | 3.13 | ✅ Compatible |
| BLAS library | `libatlas-base-dev` | `libopenblas-dev` | ✅ Fixed |

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

### 4. Dialout Group (for GPS USB access)
- **Command:** `sudo usermod -a -G dialout pi`
- **Status:** ✅ Added (applied via `setup_pi.sh`)

---

## 📷 Camera Setup

### Hardware Detection
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

### Key Issue Resolved: V4L2 → picamera2

On Pi 5 Trixie, `cv2.VideoCapture(0)` (V4L2) **does NOT work** with CSI cameras.
The fix: use `picamera2` (Python wrapper for libcamera).

**Python camera capture (confirmed working):**
```
[CAM] Trying picamera2 (libcamera)...
[1:03:40.804520077] [35056]  INFO Camera camera_manager.cpp:340 libcamera v0.7.1
[OK] Camera opened (picamera2): 640x480
```

The `PiCameraCapture` wrapper class in `run_raspberry_pi.py` provides `.read()/.release()` API identical to OpenCV, with automatic RGB→BGR conversion for YOLO compatibility.

---

## 🛰️ GPS Setup

### Hardware
- **Module:** u-blox NEO-6M-0-001 (NOT NEO-8M as originally guessed from photos)
- **Connection:** Via Micro USB (NOT via GPIO/UART as in original CLAUDE.md)
- **Has integrated patch antenna** (no external antenna needed)
- **Accuracy:** ~2.5-5 meters in open sky

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

### Device Path: `/dev/ttyACM0`
```bash
ls /dev/ttyACM*
# Output: /dev/ttyACM0
```

u-blox modules use CDC-ACM driver, not USB-serial.

### gpsd Configuration
File: `/etc/default/gpsd`
```
START_DAEMON="true"
USBAUTO="true"
DEVICES="/dev/ttyACM0"
GPSD_OPTIONS="-n"
GPSD_SOCKET="/var/run/gpsd.sock"
```

### GPS Fix — ✅ CONFIRMED WORKING
```
[OK] GPS connected (NEO-6M)
[OK] GPS fix: 29.106436, 31.130878
```

First fix acquired successfully. Coordinates confirmed valid (within Egypt bounds).

### GPS Coordinate Validation
The code validates all GPS readings against Egypt geographic bounds:
```python
EGYPT_LAT_MIN, EGYPT_LAT_MAX = 22.0, 32.0
EGYPT_LON_MIN, EGYPT_LON_MAX = 25.0, 37.0
```
Rejects: `(0,0)`, `None`, coordinates outside Egypt (multipath errors).

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
- **Status Update:** During testing with YOLOv8 inference, the temperature reached **79°C**, which is dangerously close to the soft throttle limit (80°C).
- **Action Taken:** We are purchasing the [Official Active Cooler Set (RAM Electronics)](https://www.ram-e-shop.com/ar/shop/hs-p5-active-set-raspberry-pi-5-complete-active-cooler-set-9182?srsltid=AfmBOoqU-hoRSQs5ymcaRiJZzE5xM9r82dSzwmY13UiJvr220dt3iHvi) to provide active cooling and ensure stable performance under load.

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

## 🚀 Upcoming Hardware & Optimization Plans

### 1. Detection Distance & AI Model Enhancement
- **Challenge:** We need to evaluate the maximum distance at which the camera can detect bumps accurately. If the detection distance is too short, the driver won't have enough time to react.
- **Potential Solutions:**
  - **Increase Camera Resolution:** Higher resolution (e.g., 1280x720 instead of 640x480) allows capturing smaller/further bumps, though it will increase processing time (lower FPS).
  - **Upgrade AI Model:** If YOLOv8 struggles with long-distance detection, we will consider upgrading to **YOLO11**. YOLO11 offers significantly better small-object detection and improved accuracy, which is ideal for spotting bumps from far away.

### 2. In-Car Power Supply (Battery / Power Bank)
- **Challenge:** The system will be deployed in a car, meaning we cannot use the official 27W wall adapter. Since Raspberry Pi-specific Power HATs are not easily available in Egypt, we need a manual power solution.
- **Power Requirements (Pi 5):** 
  - Ideal input: **5V / 5A (25W)**.
  - Using less than 5A (e.g., standard 3A) will restrict USB peripherals and may cause under-voltage warnings under heavy AI load.
- **Calculations & Solutions:**
  - **Power = Voltage × Current** (P = V × I). To deliver 25W, we need exactly 5V and 5A.
  - **Solution A (Power Bank):** A high-end power bank that explicitly supports **Power Delivery (PD) providing 5V at 5A**. (Note: Most generic fast-charging power banks step up the voltage to 9V/12V but only provide 3A at 5V, which is insufficient).
  - **Solution B (Car Battery Buck Converter):** Connecting to the car's 12V system (cigarette lighter socket) and using a **Step-Down (Buck) Converter module**. 
    - We need a module that converts **12V-24V input to exactly 5V output**, rated for **at least 5A to 10A** (to keep a safe margin so the module doesn't overheat). This is the most reliable method for continuous car use.

---

## 📂 Project Directory (actual, on Pi)

```
/home/pi/bump_detection/
├── Production/
│   ├── api_server.py          # FastAPI v3.0 (dedup + device tracking)
│   ├── best.pt                # YOLOv8 model (6MB)
│   ├── requirements.txt       # Python deps with version pins
│   ├── run_raspberry_pi.py    # Main detection script
│   ├── run_laptop.py          # Laptop testing (mock GPS)
│   ├── setup_pi.sh            # Full Pi setup (Trixie-adapted)
│   ├── start.sh               # System launcher (API + detection)
│   ├── FOR_FLUTTER_TEAM.md    # Flutter API integration guide
│   ├── AGENT_FINAL_V3.md      # Implementation spec (completed)
│   ├── RPI_SETUP_LOG.md       # This file
│   ├── README.txt             # Quick start guide
│   ├── bumps_data.json        # ← THE database (persisted bumps)
│   ├── device_id.txt          # Auto-generated device identifier
│   └── sounds/                # Auto-generated on first run
│       ├── beep_success.wav   # Single beep (bump recorded)
│       └── beep_warning.wav   # Double beep (no GPS)
└── bump_env/                  # Python venv (--system-site-packages)
```

---

## 🔧 Software Features (all implemented)

### Detection Script (`run_raspberry_pi.py`)

| Feature | Description |
|---------|-------------|
| **YOLOv8 inference** | Processes every 3rd frame at 640x480, confidence threshold 0.5 |
| **picamera2 backend** | Native libcamera support for Pi 5 Trixie (V4L2 fallback available) |
| **GPS validation** | Rejects (0,0), None, and coordinates outside Egypt bounds |
| **Local dedup** | Skips if bump is within 8m of an already-recorded location this session |
| **Cooldown** | 3-second minimum between detections |
| **Audio feedback** | Success beep (recorded) / Warning double-beep (no GPS) via pygame |
| **Device ID** | MAC-derived, persisted to `device_id.txt`, sent with every API call |
| **Headless mode** | `ENABLE_DISPLAY = False` by default (no GUI needed) |
| **Graceful failure** | Audio, GPS, API — all fail gracefully without crashing |

### API Server (`api_server.py` v3.0)

| Feature | Description |
|---------|-------------|
| **Spatial dedup** | Haversine distance check — bumps within 8m are merged |
| **reports_count** | Tracks total number of reports per bump |
| **reported_by** | List of unique device IDs that confirmed each bump |
| **min_confirmations** | `GET /get_bumps?min_confirmations=2` filters unreliable bumps |
| **CORS** | Fully open for Flutter app access |
| **Persistence** | JSON file (`bumps_data.json`) — single source of truth |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Health check + bump count |
| POST | `/report_bump` | Report new bump (auto-dedup) |
| GET | `/get_bumps?limit=N&min_confirmations=M` | Get bumps for Flutter app |
| DELETE | `/clear_bumps` | Reset database (testing only) |

---

## 🏃 First Successful Run

```
============================================================
  BUMP DETECTION - Raspberry Pi 5 Production
============================================================
  Model:   best.pt
  Camera:  Pi Camera Module v2
  GPS:     NEO-6M
  API:     http://127.0.0.1:8000
  Device:  pi_xxxxxxxxxxxx
  Display: Off (headless)
============================================================
[OK] API server connected
[OK] Model loaded
[OK] GPS connected (NEO-6M)
[OK] GPS fix: 29.106436, 31.130878
[OK] Camera opened (picamera2): 640x480
[OK] Audio feedback initialized

[RUN] System running. Press Ctrl+C to stop.

[BUMP #1] conf=0.82 GPS=(29.106436, 31.130878) [API: NEW]
```

✅ All subsystems operational:
- Camera: picamera2 640x480 ✅
- GPS: Fix acquired, coordinates valid ✅
- YOLO: Model loaded and detecting ✅
- API: Server running, bumps stored ✅
- Audio: Feedback beeps working ✅

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

### Project
```bash
cd ~/bump_detection
source bump_env/bin/activate
cd Production
./start.sh                               # start full system
curl http://localhost:8000/               # test API
curl http://localhost:8000/get_bumps      # get all bumps
```

### SSH from laptop (Ubuntu)
```bash
ssh [email protected]

# File transfer
scp file.py [email protected]:~/bump_detection/Production/
```

---

## ✅ Verified Working

- [x] OS boot from SD card
- [x] WiFi connection
- [x] SSH access (from same network)
- [x] Camera detection (imx219 via rpicam-hello)
- [x] Camera capture in Python (picamera2 — 640x480)
- [x] GPS USB recognition (u-blox 6, `/dev/ttyACM0`)
- [x] GPS fix acquired (29.1064°N, 31.1309°E)
- [x] GPS coordinate validation (Egypt bounds)
- [x] gpsd service running
- [x] Mouse + keyboard
- [x] HDMI display output
- [x] Thermal in idle (59°C, no throttling)
- [x] YOLOv8 inference running (best.pt loaded, detecting bumps)
- [x] FastAPI server v3.0 functional (dedup + device tracking)
- [x] Audio feedback (success + warning beeps via pygame)
- [x] Device ID generation + persistence
- [x] Local dedup (same bump at same location = 1 record)
- [x] Spatial dedup on API (8m Haversine radius)
- [x] setup_pi.sh adapted for Trixie + USB GPS
- [x] requirements.txt created with version pins
- [x] start.sh with trap cleanup

## ⏳ Pending

- [ ] Thermal under sustained load (need stress test during driving)
- [ ] Mobile app (Flutter) connection test
- [ ] Outdoor driving test (real road conditions)
- [ ] Multi-device dedup test (when 2nd Pi or cloud migration)
