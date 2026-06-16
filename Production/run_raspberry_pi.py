#!/usr/bin/env python3
"""
RASPBERRY PI 5 - Bump Detection with Real GPS (Production)
Hardware: Pi 5 (8GB) + Pi Camera Module v2 + NEO-6M GPS
"""

from ultralytics import YOLO
import cv2
import time
import threading
import json
import os
import sys
import uuid
import wave
import struct
from datetime import datetime, timezone
import requests
import numpy as np

# ==================== CONFIGURATION ====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

# Model: prefer NCNN (4x faster on Pi), fallback to .pt
NCNN_MODEL = os.path.join(SCRIPT_DIR, "best_ncnn_model")
PT_MODEL = os.path.join(SCRIPT_DIR, "best.pt")
MODEL_PATH = NCNN_MODEL if os.path.isdir(NCNN_MODEL) else PT_MODEL

CONFIDENCE_THRESHOLD = 0.5
PROCESS_EVERY_N_FRAMES = 2  # Reduced from 3 (NCNN is faster)
BUMP_COOLDOWN_SECONDS = 3
ENABLE_DISPLAY = False

API_URL = "http://127.0.0.1:8000"

# Camera settings for Pi Camera Module v2
# NOTE: 1280x960 uses the FULL sensor (wide FOV).
# 640x480 used a center crop (narrow/zoomed). YOLO resizes internally to 640x640.
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 960
CAMERA_FPS = 30

# Audio feedback
AUDIO_ENABLED = True
SOUNDS_DIR = os.path.join(SCRIPT_DIR, "sounds")
SOUND_SUCCESS = os.path.join(SOUNDS_DIR, "beep_success.wav")
SOUND_WARNING = os.path.join(SOUNDS_DIR, "beep_warning.wav")

# Egypt geographic bounds (rough)
EGYPT_LAT_MIN, EGYPT_LAT_MAX = 22.0, 32.0
EGYPT_LON_MIN, EGYPT_LON_MAX = 25.0, 37.0

# Local dedup: skip if bump is within this radius of an already-recorded bump
# Must match the API server's DEDUP_RADIUS_METERS
DEDUP_RADIUS_METERS = 8


# ==================== GEO UTILS ====================
def is_valid_egypt_location(lat, lon):
    """Reject obviously bad GPS readings."""
    if lat is None or lon is None:
        return False
    if lat == 0.0 or lon == 0.0:
        return False
    if not (EGYPT_LAT_MIN <= lat <= EGYPT_LAT_MAX):
        return False
    if not (EGYPT_LON_MIN <= lon <= EGYPT_LON_MAX):
        return False
    return True


def haversine_distance(lat1, lon1, lat2, lon2):
    """Distance in meters between two GPS coordinates."""
    import math
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def is_near_recorded_bump(lat, lon, recorded_bumps, radius=DEDUP_RADIUS_METERS):
    """Check if (lat, lon) is within radius meters of any already-recorded bump."""
    for rlat, rlon in recorded_bumps:
        if haversine_distance(lat, lon, rlat, rlon) <= radius:
            return True
    return False


# ==================== DEVICE ID ====================
def get_or_create_device_id():
    """Stable device ID, generated once and persisted."""
    device_id_file = os.path.join(SCRIPT_DIR, "device_id.txt")
    if os.path.exists(device_id_file):
        with open(device_id_file, 'r') as f:
            return f.read().strip()
    device_id = f"pi_{uuid.getnode():012x}"  # MAC-derived, stable
    with open(device_id_file, 'w') as f:
        f.write(device_id)
    return device_id


# ==================== AUDIO FEEDBACK ====================
class AudioFeedback:
    """Non-blocking audio feedback for bump detection events.
    Uses pygame.mixer. Fails gracefully if no audio device found."""

    def __init__(self, enabled=True):
        self.available = False
        if not enabled:
            print("[AUDIO] Disabled by config")
            return
        self._init_audio()

    def _init_audio(self):
        try:
            import pygame
            pygame.mixer.init()
            self._pygame = pygame
            self._generate_sounds()
            self._snd_success = pygame.mixer.Sound(SOUND_SUCCESS)
            self._snd_warning = pygame.mixer.Sound(SOUND_WARNING)
            self.available = True
            print("[OK] Audio feedback initialized")
        except Exception as e:
            print(f"[WARN] Audio not available: {e}")
            print("       (detection continues without sound)")

    def _generate_sounds(self):
        """Generate WAV sound files programmatically if they don't exist."""
        os.makedirs(SOUNDS_DIR, exist_ok=True)

        if not os.path.exists(SOUND_SUCCESS):
            self._create_wav(SOUND_SUCCESS, frequency=800, duration_ms=200, count=1)

        if not os.path.exists(SOUND_WARNING):
            self._create_wav(SOUND_WARNING, frequency=500, duration_ms=150, count=2, gap_ms=100)

    @staticmethod
    def _create_wav(filepath, frequency, duration_ms, count=1, gap_ms=0):
        """Generate a simple beep WAV file."""
        sample_rate = 22050
        samples_per_beep = int(sample_rate * duration_ms / 1000)
        samples_gap = int(sample_rate * gap_ms / 1000)

        all_samples = []
        for i in range(count):
            for s in range(samples_per_beep):
                t = s / sample_rate
                # Sine wave with fade in/out
                amplitude = 0.6
                fade_len = int(samples_per_beep * 0.1)
                if s < fade_len:
                    amplitude *= s / fade_len
                elif s > samples_per_beep - fade_len:
                    amplitude *= (samples_per_beep - s) / fade_len
                value = int(amplitude * 32767 * np.sin(2 * np.pi * frequency * t))
                all_samples.append(value)
            if i < count - 1:
                all_samples.extend([0] * samples_gap)

        with wave.open(filepath, 'w') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(struct.pack(f'<{len(all_samples)}h', *all_samples))

    def play_success(self):
        """Single beep — bump recorded successfully."""
        if self.available:
            try:
                self._snd_success.play()
            except Exception:
                pass

    def play_warning(self):
        """Double beep — bump detected but NOT recorded (no GPS)."""
        if self.available:
            try:
                self._snd_warning.play()
            except Exception:
                pass


# ==================== GPS THREAD ====================
class GPSReader:
    """Non-blocking GPS reader using a background thread"""

    def __init__(self):
        self.latitude = None
        self.longitude = None
        self.altitude = 0.0
        self.has_fix = False
        self.available = False
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._connect()

    def _connect(self):
        try:
            import gps as gps_module
            self._gps_module = gps_module
            self.session = gps_module.gps(mode=gps_module.WATCH_ENABLE | gps_module.WATCH_NEWSTYLE)
            self.available = True
            self._running = True
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
            print("[OK] GPS connected (NEO-6M)")
        except ImportError:
            print("[ERROR] gps module not installed. Run: sudo apt install python3-gps")
            self.available = False
        except Exception as e:
            print(f"[ERROR] GPS connection failed: {e}")
            print("        Make sure gpsd is running: sudo systemctl start gpsd")
            self.available = False

    def _read_loop(self):
        while self._running:
            try:
                report = self.session.next()
                if report['class'] == 'TPV':
                    lat = getattr(report, 'lat', None)
                    lon = getattr(report, 'lon', None)
                    if lat is not None and lon is not None:
                        if is_valid_egypt_location(lat, lon):
                            with self._lock:
                                self.latitude = lat
                                self.longitude = lon
                                self.altitude = getattr(report, 'alt', 0.0)
                                self.has_fix = True
                        # else: invalid reading — keep has_fix unchanged
            except StopIteration:
                time.sleep(0.5)
            except Exception:
                time.sleep(0.5)

    def get_location(self):
        with self._lock:
            if not self.has_fix:
                return None
            return {
                'latitude': self.latitude,
                'longitude': self.longitude,
                'altitude': self.altitude if self.altitude else 0.0,
                'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }

    def wait_for_fix(self, timeout=60):
        if not self.available:
            return False
        print(f"[GPS] Waiting for satellite fix (max {timeout}s)...")
        start = time.time()
        while time.time() - start < timeout:
            if self.has_fix:
                loc = self.get_location()
                print(f"[OK] GPS fix: {loc['latitude']:.6f}, {loc['longitude']:.6f}")
                return True
            time.sleep(1)
        print("[WARN] No GPS fix within timeout. Will keep trying in background.")
        return False

    def close(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self.available:
            try:
                self.session.close()
            except Exception:
                pass


# ==================== CAMERA ====================
class PiCameraCapture:
    """Wrapper that provides .read()/.release() API like OpenCV,
    but uses picamera2 (libcamera stack) which works on Pi 5 Trixie."""

    def __init__(self, width, height):
        from picamera2 import Picamera2
        self.picam2 = Picamera2()
        # Use BGR888 — gives direct BGR output (no conversion needed for OpenCV/YOLO)
        config = self.picam2.create_preview_configuration(
            main={"size": (width, height), "format": "BGR888"}
        )
        self.picam2.configure(config)
        self.picam2.start()
        # Let auto-exposure settle
        time.sleep(1)

    def read(self):
        """Returns (success, frame) like cv2.VideoCapture.read()"""
        try:
            frame = self.picam2.capture_array()
            # BGR888 format → already BGR, no conversion needed
            return True, frame
        except Exception:
            return False, None

    def release(self):
        try:
            self.picam2.close()
        except Exception:
            pass


def open_camera():
    """Open Pi Camera Module v2 with multiple fallback methods"""

    # Method 1: picamera2 (native libcamera — works on Pi 5 Trixie)
    print("[CAM] Trying picamera2 (libcamera)...")
    try:
        cap = PiCameraCapture(CAMERA_WIDTH, CAMERA_HEIGHT)
        ret, frame = cap.read()
        if ret and frame is not None:
            h, w = frame.shape[:2]
            print(f"[OK] Camera opened (picamera2): {w}x{h}")
            return cap
        cap.release()
    except ImportError:
        print("[CAM] picamera2 not installed, trying OpenCV fallback...")
    except Exception as e:
        print(f"[CAM] picamera2 failed: {e}, trying OpenCV fallback...")

    # Method 2: OpenCV V4L2 (fallback)
    print("[CAM] Trying OpenCV V4L2...")
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"[OK] Camera opened (V4L2): {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
            return cap
        cap.release()

    # Method 3: OpenCV default backend
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"[OK] Camera opened (default): {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
            return cap
        cap.release()

    return None


# ==================== API REPORTING ====================
def report_to_api(location, confidence, device_id):
    """Report bump to API. Returns (success, status) where status is 'new'/'merged'/'error'."""
    try:
        data = {
            "latitude": location['latitude'],
            "longitude": location['longitude'],
            "confidence": confidence,
            "timestamp": location['timestamp'],
            "altitude": location.get('altitude'),
            "device_id": device_id,
        }
        response = requests.post(f"{API_URL}/report_bump", json=data, timeout=2)
        if response.status_code == 200:
            result = response.json()
            return True, result.get("status", "success")
        return False, "error"
    except Exception:
        return False, "error"


def check_api_server():
    """Check if API server is reachable"""
    try:
        r = requests.get(f"{API_URL}/", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


# ==================== MAIN ====================
def main():
    # --- Device ID ---
    DEVICE_ID = get_or_create_device_id()

    print("=" * 60)
    print("  BUMP DETECTION - Raspberry Pi 5 Production")
    print("=" * 60)
    print(f"  Model:   {os.path.basename(MODEL_PATH)}")
    print(f"  Camera:  Pi Camera Module v2")
    print(f"  GPS:     NEO-6M")
    print(f"  API:     {API_URL}")
    print(f"  Device:  {DEVICE_ID}")
    print(f"  Display: {'On' if ENABLE_DISPLAY else 'Off (headless)'}")
    print("=" * 60)

    # --- Check model file ---
    if not os.path.exists(MODEL_PATH):
        print(f"\n[ERROR] Model not found: {MODEL_PATH}")
        print("        Make sure best.pt exists in Production/")
        sys.exit(1)

    # --- Check API server ---
    if not check_api_server():
        print("\n[WARN] API server not reachable at", API_URL)
        print("       Start it with: python Production/api_server.py")
        print("       Continuing without API (bumps saved locally only)...")
        api_available = False
    else:
        print("[OK] API server connected")
        api_available = True

    # --- Load YOLO model ---
    print("\n[MODEL] Loading YOLO model...")
    model = YOLO(MODEL_PATH)
    print("[OK] Model loaded")

    # --- Initialize Audio ---
    audio = AudioFeedback(enabled=AUDIO_ENABLED)

    # --- Initialize GPS ---
    gps = GPSReader()
    if gps.available:
        gps.wait_for_fix(timeout=30)

    # --- Open camera ---
    cap = open_camera()
    if cap is None:
        print("\n[ERROR] Could not open camera!")
        print("        Check: sudo raspi-config -> Interface -> Camera -> Enable")
        print("        Check: ls /dev/video*")
        print("        Check: rpicam-hello --timeout 2000")
        gps.close()
        sys.exit(1)

    # --- Main loop ---
    frame_counter = 0
    bump_count = 0
    merge_count = 0
    recorded_locations = []  # (lat, lon) of bumps recorded this session for local dedup
    last_bump_time = 0
    no_gps_skips = 0
    fps_counter = 0
    fps_time = time.time()
    fps = 0

    print("\n[RUN] System running. Press Ctrl+C to stop.\n")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            frame_counter += 1

            # FPS calculation (every 30 frames)
            fps_counter += 1
            if fps_counter >= 30:
                now = time.time()
                fps = fps_counter / (now - fps_time)
                fps_time = now
                fps_counter = 0

            # Process every N frames
            if frame_counter % PROCESS_EVERY_N_FRAMES != 0:
                continue

            # Run YOLO
            results = model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)

            # Check detections
            if len(results[0].boxes) > 0:
                highest_conf = max(float(box.conf[0]) for box in results[0].boxes)

                # Cooldown check
                if time.time() - last_bump_time > BUMP_COOLDOWN_SECONDS:
                    location = gps.get_location()

                    # REQUIRE GPS fix — a bump without coordinates is useless
                    if location is None:
                        no_gps_skips += 1
                        audio.play_warning()
                        if no_gps_skips <= 5:
                            print(f"[SKIP] Bump detected (conf={highest_conf:.2f}) but NO GPS fix — not recorded")
                        elif no_gps_skips == 6:
                            print("[SKIP] (suppressing further no-GPS messages...)")
                        last_bump_time = time.time()
                        continue

                    # LOCAL DEDUP: skip if we already recorded a bump at this location
                    lat, lon = location['latitude'], location['longitude']
                    if is_near_recorded_bump(lat, lon, recorded_locations):
                        last_bump_time = time.time()
                        continue  # silently skip — same spot, no need to spam

                    last_bump_time = time.time()
                    recorded_locations.append((lat, lon))

                    # Report to API
                    api_status = ""
                    if api_available:
                        sent, status = report_to_api(location, highest_conf, DEVICE_ID)
                        if sent:
                            if status == "merged":
                                merge_count += 1
                                api_status = " [API: KNOWN BUMP]"
                            else:
                                bump_count += 1
                                api_status = " [API: NEW]"
                        else:
                            bump_count += 1
                            api_status = " [API FAIL]"
                    else:
                        bump_count += 1

                    audio.play_success()
                    total = bump_count + merge_count
                    print(f"[BUMP #{total}] conf={highest_conf:.2f} "
                          f"GPS=({lat:.6f}, {lon:.6f})"
                          f"{api_status}")

            # Display (if enabled)
            if ENABLE_DISPLAY:
                annotated = results[0].plot() if frame_counter % PROCESS_EVERY_N_FRAMES == 0 else frame
                cv2.putText(annotated, f"FPS:{fps:.1f} Bumps:{bump_count}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.imshow("Bump Detection", annotated)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            else:
                time.sleep(0.005)

    except KeyboardInterrupt:
        print("\n\n[STOP] Shutting down...")

    # --- Cleanup ---
    cap.release()
    if ENABLE_DISPLAY:
        cv2.destroyAllWindows()
    gps.close()

    # --- Session Summary ---
    print("\n" + "=" * 60)
    print("  SESSION SUMMARY")
    print("=" * 60)
    print(f"  New bumps:            {bump_count}")
    print(f"  Known bumps (merged): {merge_count}")
    print(f"  Frames processed:     {frame_counter}")
    print(f"  GPS available:        {'Yes' if gps.has_fix else 'No'}")
    if no_gps_skips > 0:
        print(f"  Skipped (no GPS):     {no_gps_skips}")
    print(f"  Database:             bumps_data.json (via API)")
    print("=" * 60)
    print("  Done!")


if __name__ == "__main__":
    main()
