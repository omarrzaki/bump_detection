# Bump Detection - Raspberry Pi 5 Full Project Log

> هذا الملف يوثق كل الخطوات اللي اتعملت في إعداد الـ Raspberry Pi 5 للـ Bump Detection Project، من أول تثبيت النظام لحد المناقشة النهائية.
> آخر تحديث: 2026-06-25 (بعد مناقشة المشروع ✅)

---

## 📋 Project Overview

- **Project:** AI-powered speed bump detection for Egyptian roads (ADAS)
- **Model:** YOLO11n — trained on 4,907 images, exported to NCNN for ARM optimization
- **Architecture:** Detection + FastAPI server on Pi → Flutter mobile app via REST
- **API Version:** v3.0 (spatial dedup, device tracking, min_confirmations, thread-safe)
- **Camera Backend:** `picamera2` (libcamera stack — required for Pi 5 Trixie)
- **Final Status:** ✅ Project discussed and completed successfully

---

## 🖥️ Hardware Inventory

| Component | Status | Notes |
|-----------|--------|-------|
| Raspberry Pi 5 | ✅ | 8GB model |
| SD Card | ✅ Flashed | Raspberry Pi OS Full 64-bit |
| Official 27W USB-C PSU | ✅ | Original Raspberry Pi |
| Pi Camera Module v2 (imx219) | ✅ Working | Via picamera2, 640x480 (full sensor via 1280x960 available) |
| u-blox NEO-6M GPS | ✅ GPS Fix acquired | Module: `NEO-6M-0-001`, USB `/dev/ttyACM0` |
| Micro USB cable (for GPS) | ✅ | Data-capable cable |
| Micro HDMI to HDMI cable | ✅ | For local display |
| HP Monitor | ✅ | Connected via HDMI 0 |
| Wireless Mouse (Attack Shark X11) | ✅ | High DPI, working fine |
| USB Keyboard | ✅ | SINO WEALTH Gaming KB |
| Passive Heatsink (4x copper pads) | ✅ Installed | Hit 79°C under AI load — Active Cooler purchased |
| Active Cooler (official) | ✅ Purchased | [RAM Electronics link](https://www.ram-e-shop.com/ar/shop/hs-p5-active-set-raspberry-pi-5-complete-active-cooler-set-9182) — must remove passive heatsink first |

---

## 🐧 Operating System

### Critical: NOT Bookworm — Using Trixie

```
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
VERSION_ID="13"
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
- **Hostname:** `raspberry`
- **Username:** `pi`
- **SSH:** ✅ Enabled with password authentication
- **Wi-Fi:** ✅ Configured (EG country code)
- **Locale:** Africa/Cairo, Arabic keyboard layout

---

## 🌐 Network Configuration

- **IPs assigned:** `192.168.1.40`, `192.168.1.39`
- **Internet:** ✅ Working
- **mDNS hostname:** `raspberry.local`

### SSH from laptop:
```bash
ssh [email protected]
```

---

## ⚙️ System Tweaks Applied

1. **USB Current Limit Disabled** — allows up to 1.6A on USB peripherals (safe with 27W PSU)
2. **Mouse Lag Fixed** — moved to USB 2.0 port + increased DPI on Attack Shark X11
3. **Keyboard Layout** — Arabic + English both available
4. **Dialout Group** — `sudo usermod -a -G dialout pi` (required for GPS USB access)

---

## 📷 Camera Setup

### Hardware Detection
```bash
rpicam-hello --list-cameras
```

```
0 : imx219 [3280x2464 10-bit RGGB]
    Modes: 'SRGGB10_CSI2P' : 640x480 [206.65 fps - (1000, 752)/1280x960 crop]
                             1640x1232 [41.85 fps - (0, 0)/3280x2464 crop]
                             1920x1080 [47.57 fps - (680, 692)/1920x1080 crop]
                             3280x2464 [21.19 fps - (0, 0)/3280x2464 crop]
```

### Key Issue Resolved: V4L2 → picamera2

On Pi 5 Trixie, `cv2.VideoCapture(0)` (V4L2) **does NOT work** with CSI cameras.
The fix: use `picamera2` (Python wrapper for libcamera).

### ⚠️ Camera Color (picamera2 format quirk)

picamera2 format names are **byte-order-reversed** vs the numpy array:
- `format="RGB888"` → `capture_array()` returns **BGR** (correct for OpenCV/YOLO)
- `format="BGR888"` → `capture_array()` returns **RGB** (causes blue tint!)

**Correct setting:** Use `format="RGB888"` with **NO** `cv2.cvtColor()` conversion.

The `PiCameraCapture` wrapper class in `run_raspberry_pi.py` provides `.read()/.release()` API identical to OpenCV.

### Resolution vs Field of View

| Resolution | Sensor Mode | FOV | Use Case |
|-----------|------------|-----|----------|
| 640x480 (current) | Center crop (1000,752)/1280x960 | Narrow/zoomed | Default — fast inference |
| 1280x960 | Full sensor (0,0)/3280x2464 | Wide | Better detection distance |

To switch, change `CAMERA_WIDTH` and `CAMERA_HEIGHT` in `run_raspberry_pi.py`. YOLO resizes to 640x640 internally regardless.

---

## 🛰️ GPS Setup

### Hardware
- **Module:** u-blox NEO-6M-0-001
- **Connection:** Via Micro USB (NOT GPIO/UART — no soldering needed)
- **Accuracy:** ~2.5-5 meters in open sky

### USB Recognition
```
Bus 003 Device 004: ID 1546:01a6 U-Blox AG [u-blox 6]
```
Device path: `/dev/ttyACM0` (CDC-ACM driver)

### gpsd Configuration (`/etc/default/gpsd`)
```
START_DAEMON="true"
USBAUTO="true"
DEVICES="/dev/ttyACM0"
GPSD_OPTIONS="-n"
GPSD_SOCKET="/var/run/gpsd.sock"
```

### GPS Fix — ✅ CONFIRMED WORKING
```
[OK] GPS fix: 29.106436, 31.130878
```

### GPS Coordinate Validation
All GPS readings validated against Egypt geographic bounds:
```python
EGYPT_LAT = (22.0, 32.0)
EGYPT_LON = (25.0, 37.0)
```
Rejects: `(0,0)`, `None`, coordinates outside Egypt.

---

## 🌡️ Thermal Status

| State | Temperature | Throttling |
|-------|-------------|------------|
| Idle (no load) | 59.3°C | ✅ None |
| Under YOLO inference | **79°C** | ⚠️ Near soft throttle (80°C) |

### Solution: Active Cooler
- Passive heatsink (4x copper pads) alone is **insufficient** for sustained AI workload
- Purchased the [Official Active Cooler Set](https://www.ram-e-shop.com/ar/shop/hs-p5-active-set-raspberry-pi-5-complete-active-cooler-set-9182)
- **Installation:** Must remove passive heatsink pads first (heat them with a hair dryer to soften adhesive), then mount the active cooler directly on the SoC. Connect fan cable to the 4-pin FAN header on the board (auto-controlled)

### Thermal Thresholds (Pi 5)
| Temp | Status |
|------|--------|
| < 60°C | ✅ Ideal |
| 60–75°C | ✅ Normal under load |
| 75–80°C | ⚠️ Soft throttle begins |
| 80–85°C | 🟠 Significant throttling |
| > 85°C | 🔴 Hard throttle (50% speed) |
| > 90°C | 🚨 Shutdown protection |

---

## 📂 Project Directory (final structure)

```
/home/pi/bump_detection/
├── Production/
│   ├── api_server.py             # FastAPI v3.0 (thread-safe, atomic writes, dedup)
│   ├── best_ncnn_model/          # YOLO11n NCNN export (primary — 4x faster on ARM)
│   │   ├── model.ncnn.bin        # Weights (10MB)
│   │   ├── model.ncnn.param      # Architecture
│   │   └── metadata.yaml         # Model metadata (class: speed-bumps)
│   ├── best_yolo11.pt            # YOLO11n PyTorch (.pt fallback)
│   ├── best.pt                   # Original YOLOv8 model (legacy)
│   ├── best_v8_backup.pt         # YOLOv8 backup before migration
│   ├── run_raspberry_pi.py       # Main detection script (654 lines)
│   ├── run_laptop.py             # Laptop testing (mock GPS, in-process API)
│   ├── requirements.txt          # Python deps with version pins
│   ├── setup_pi.sh               # Full Pi setup (Trixie-adapted)
│   ├── start.sh                  # System launcher (API + detection with trap cleanup)
│   ├── FOR_FLUTTER_TEAM.md       # Flutter API integration guide
│   ├── RPI_SETUP_LOG.md          # This file
│   ├── STUDY_GUIDE.md            # Comprehensive study guide (Arabic/English)
│   ├── Book/                     # Graduation project documentation (PDFs)
│   ├── bumps_data.json           # ← THE database (persisted bumps, single source of truth)
│   ├── device_id.txt             # Auto-generated device identifier
│   └── sounds/                   # Auto-generated on first run
│       ├── beep_success.wav      # Single beep (bump recorded)
│       └── beep_warning.wav      # Double beep (no GPS)
└── bump_env/                     # Python venv (--system-site-packages)
```

---

## 🔧 Software Features (all implemented)

### Detection Script (`run_raspberry_pi.py`)

| Feature | Description |
|---------|-------------|
| **YOLO11n + NCNN** | Primary: NCNN (4x faster on ARM), fallback chain: YOLO11 .pt → YOLOv8 .pt |
| **Hybrid confidence tiering** | HIGH (≥0.75) = instant record, MEDIUM (0.60-0.75) = needs 2 confirmations in 1s, below 0.55 = ignored |
| **picamera2 backend** | Native libcamera support for Pi 5 Trixie (RGB888 format = BGR array) |
| **GPS validation** | Rejects (0,0), None, and coordinates outside Egypt bounds |
| **Local dedup** | Skips if bump is within 8m of an already-recorded location this session |
| **Cooldown** | 3-second minimum between detections |
| **Audio feedback** | Success beep / Warning double-beep via pygame (auto-generated WAV files) |
| **Device ID** | MAC-derived, persisted to `device_id.txt`, sent with every API call |
| **Headless heartbeat** | Prints `[ALIVE]` status every 5 seconds when display is off |
| **Graceful cleanup** | `try/finally` ensures camera + GPS are released even on crash |

### API Server (`api_server.py` v3.0)

| Feature | Description |
|---------|-------------|
| **Spatial dedup** | Haversine distance — bumps within 8m are merged |
| **Thread-safe writes** | `threading.Lock` + atomic `os.replace()` prevents data corruption |
| **reports_count** | Tracks total reports per bump |
| **reported_by** | List of unique device IDs that confirmed each bump |
| **min_confirmations** | `GET /get_bumps?min_confirmations=2` filters unreliable bumps |
| **CORS** | Fully open for Flutter app access |
| **Background mode** | Can run in-process as daemon thread (used by `run_laptop.py`) |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Health check + bump count |
| POST | `/report_bump` | Report new bump (auto-dedup, returns `new`/`merged` status) |
| GET | `/get_bumps?limit=N&min_confirmations=M` | Get bumps for Flutter app |
| DELETE | `/clear_bumps` | Reset database (testing only) |

---

## Phase 1: Initial Hardware Setup & OS Configuration

- Flashed Raspberry Pi OS Full 64-bit (Debian 13 Trixie)
- Connected all peripherals (camera, GPS, display, keyboard, mouse)
- Configured Wi-Fi, SSH, user permissions
- Resolved USB mouse lag, keyboard layout issues
- Verified camera via `rpicam-hello`, GPS via `lsusb`

## Phase 2: Software Deployment & First Run

- Created `setup_pi.sh` adapted for Trixie (libopenblas, picamera2, PEP 668 venv)
- Built `PiCameraCapture` wrapper (picamera2 → OpenCV-compatible API)
- Deployed YOLOv8 model, FastAPI server, GPS polling thread
- First successful detection session with GPS fix confirmed

## Phase 3: Detection Logic Refinement

- **Deduplication:** Implemented local spatial dedup (8m Haversine radius) — same bump at same location = 1 record per session
- **API dedup:** Server-side dedup with `reports_count` and `reported_by` tracking
- **Session cleanup:** Removed per-session JSON files — `bumps_data.json` is the single source of truth
- **Audio feedback:** pygame-based beeps (success/warning) auto-generated as WAV files
- **Device identity:** MAC-derived device ID, persisted to `device_id.txt`

## Phase 4: YOLO11 Upgrade & Performance Optimization

### Model Training (4 Progressive Rounds)

| Round | Dataset | Images | Result |
|-------|---------|--------|--------|
| 1 | Base (`detecting speed bumps.v4`) | 519 | mAP50 = 89.6% |
| 2 | + Bumps (Roboflow) | 2,038 | mAP50 = 95.4% |
| 3 | + Unmarked Bumps (filtered) | 3,207 | mAP50 = 92.7% |
| **4** | **+ RoadModel + Maquette (50x oversampled)** | **4,907** | **mAP50 = 92.2%** |

- Trained on local GTX 1660 Ti with CUDA
- Round 4 addressed **Catastrophic Forgetting** via oversampling of 12 maquette images (50x = 600 copies)
- Fine-tuned from Round 3 model to preserve existing knowledge

### NCNN Export
- Exported to NCNN format — optimized for ARM (Raspberry Pi 5)
- **~4x faster inference** compared to raw PyTorch
- Updated scripts with automatic fallback: NCNN → YOLO11 .pt → YOLOv8 .pt

## Phase 5: False Positive Reduction & Confidence Tiering

- **Problem:** Low-confidence detections (0.50-0.55) caused false positives (e.g., t-shirt patterns, columns detected as bumps)
- **Solution:** Hybrid confidence tiering system:
  - **HIGH (≥0.75):** Single frame records immediately — real bumps score 0.80+ consistently
  - **MEDIUM (0.60-0.75):** Needs 2 qualifying frames within 1 second to confirm
  - **NOISE (0.55-0.60):** Ignored — observed false positive zone
  - **FLOOR (<0.55):** Rejected entirely by YOLO
- At 40 km/h, a bump is visible for ~0.7s (3-4 processed frames) — tiering works within this window

## Phase 6: Production Hardening

- **Thread-safe API:** `threading.Lock` on write path + atomic `os.replace()` (no corrupt JSON)
- **Heartbeat:** `[ALIVE]` status line every 5 seconds in headless mode
- **Cleanup:** `try/finally` ensures camera + GPS are released even on crash (prevents locked camera requiring reboot)
- **GPS dependency:** `python3-gps` installed via APT (not pip) to avoid PyPI shadowing issues on Python 3.13
- **`task="detect"`** passed to YOLO constructor for NCNN models (suppresses metadata warning)

---

## 🚀 Hardware Upgrade Plans

### 1. In-Car Power Supply
- **Challenge:** Official 27W wall adapter can't be used in a car. Pi-specific Power HATs not available in Egypt.
- **Power Requirements:** 5V / 5A (25W) — less than 5A causes under-voltage warnings under AI load.
- **Solutions:**
  - **Power Bank:** Must explicitly support PD 5V/5A (most fast-charge banks only provide 3A at 5V)
  - **Car Buck Converter (recommended):** 12V→5V step-down module rated ≥5A, connected via cigarette lighter socket

---

## 📞 Reference Commands

### System
```bash
sudo reboot                          # restart
sudo shutdown -h now                 # safe shutdown
vcgencmd measure_temp                # CPU temperature
watch -n 2 vcgencmd measure_temp     # continuous monitoring
```

### Camera
```bash
rpicam-hello --list-cameras          # list cameras
rpicam-hello -t 10000                # 10-sec preview
rpicam-still -o test.jpg             # capture image
```

### GPS
```bash
ls /dev/ttyACM*                      # confirm device
sudo systemctl status gpsd           # service status
cgps -s                              # live GPS data
```

### Project
```bash
cd ~/bump_detection
source bump_env/bin/activate
cd Production
./start.sh                           # start full system
curl http://localhost:8000/           # test API
curl http://localhost:8000/get_bumps  # get all bumps
```

---

## ✅ Verified Working (Final Checklist)

- [x] OS boot from SD card (Debian 13 Trixie)
- [x] WiFi + SSH access
- [x] Camera detection + Python capture (picamera2)
- [x] GPS USB recognition + fix acquired (29.1064°N, 31.1309°E)
- [x] GPS coordinate validation (Egypt bounds)
- [x] gpsd service running
- [x] All peripherals (mouse, keyboard, display)
- [x] Thermal monitoring (idle 59°C, load 79°C)
- [x] YOLOv8 inference (original model)
- [x] **YOLO11n upgrade + NCNN export (4x faster on ARM)**
- [x] **Master model trained (4,907 images, mAP50 = 92.2%)**
- [x] **Maquette integration (50x oversampling, no catastrophic forgetting)**
- [x] **Hybrid confidence tiering (HIGH/MEDIUM/NOISE/FLOOR)**
- [x] **Thread-safe API with atomic writes**
- [x] FastAPI server v3.0 (dedup + device tracking)
- [x] Audio feedback (success + warning beeps via pygame)
- [x] Device ID generation + persistence
- [x] Local + API spatial dedup (8m Haversine radius)
- [x] Headless heartbeat (`[ALIVE]` every 5s)
- [x] Graceful cleanup (try/finally on camera + GPS)
- [x] setup_pi.sh adapted for Trixie + USB GPS
- [x] requirements.txt with version pins
- [x] start.sh with trap cleanup
- [x] FOR_FLUTTER_TEAM.md API guide
- [x] STUDY_GUIDE.md (comprehensive project study guide)
- [x] Book/ (graduation project PDFs)
- [x] **🎓 Project discussed successfully**