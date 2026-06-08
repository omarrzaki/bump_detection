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
from datetime import datetime, timezone
import requests

# ==================== CONFIGURATION ====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

MODEL_PATH = os.path.join(PROJECT_DIR, "runs", "detect", "train", "weights", "best.pt")

CONFIDENCE_THRESHOLD = 0.5
PROCESS_EVERY_N_FRAMES = 3
BUMP_COOLDOWN_SECONDS = 3
ENABLE_DISPLAY = False

API_URL = "http://127.0.0.1:8000"

# Camera settings for Pi Camera Module v2
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30


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
                        with self._lock:
                            self.latitude = lat
                            self.longitude = lon
                            self.altitude = getattr(report, 'alt', 0.0)
                            self.has_fix = True
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
def open_camera():
    """Open Pi Camera Module v2 with multiple fallback methods"""

    # Method 1: libcamera via V4L2 (default on Pi 5 Bookworm)
    print("[CAM] Trying Pi Camera Module v2...")
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

    # Method 2: default backend
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"[OK] Camera opened (default): {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
            return cap
        cap.release()

    # Method 3: try /dev/video1
    cap = cv2.VideoCapture(1, cv2.CAP_V4L2)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        ret, frame = cap.read()
        if ret and frame is not None:
            print("[OK] Camera opened on /dev/video1")
            return cap
        cap.release()

    return None


# ==================== API REPORTING ====================
def report_to_api(location, confidence):
    try:
        data = {
            "latitude": location['latitude'],
            "longitude": location['longitude'],
            "confidence": confidence,
            "timestamp": location['timestamp'],
            "altitude": location.get('altitude')
        }
        response = requests.post(f"{API_URL}/report_bump", json=data, timeout=2)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False
    except Exception:
        return False


def check_api_server():
    """Check if API server is reachable"""
    try:
        r = requests.get(f"{API_URL}/", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


# ==================== MAIN ====================
def main():
    print("=" * 60)
    print("  BUMP DETECTION - Raspberry Pi 5 Production")
    print("=" * 60)
    print(f"  Model:   {os.path.basename(MODEL_PATH)}")
    print(f"  Camera:  Pi Camera Module v2")
    print(f"  GPS:     NEO-6M")
    print(f"  API:     {API_URL}")
    print(f"  Display: {'On' if ENABLE_DISPLAY else 'Off (headless)'}")
    print("=" * 60)

    # --- Check model file ---
    if not os.path.exists(MODEL_PATH):
        print(f"\n[ERROR] Model not found: {MODEL_PATH}")
        print("        Make sure best.pt exists in runs/detect/train/weights/")
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
        print("        Check: libcamera-hello --timeout 2000")
        gps.close()
        sys.exit(1)

    # --- Main loop ---
    frame_counter = 0
    bump_count = 0
    bumps_log = []
    last_bump_time = 0
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
                    last_bump_time = time.time()
                    bump_count += 1

                    location = gps.get_location()

                    bump_data = {
                        'id': f"bump_{bump_count}",
                        'confidence': round(highest_conf, 4),
                        'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                        'latitude': location['latitude'] if location else None,
                        'longitude': location['longitude'] if location else None,
                        'altitude': location.get('altitude', 0.0) if location else None,
                    }
                    bumps_log.append(bump_data)

                    # Report to API
                    api_status = ""
                    if api_available and location:
                        sent = report_to_api(location, highest_conf)
                        api_status = " [API OK]" if sent else " [API FAIL]"

                    # Console output
                    if location:
                        print(f"[BUMP #{bump_count}] conf={highest_conf:.2f} "
                              f"GPS=({location['latitude']:.6f}, {location['longitude']:.6f})"
                              f"{api_status}")
                    else:
                        print(f"[BUMP #{bump_count}] conf={highest_conf:.2f} GPS=NO FIX{api_status}")

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

    # --- Save session log ---
    print("\n" + "=" * 60)
    print("  SESSION SUMMARY")
    print("=" * 60)
    print(f"  Total bumps detected: {bump_count}")
    print(f"  Frames processed:     {frame_counter}")
    print(f"  GPS available:        {'Yes' if gps.has_fix else 'No'}")

    if bumps_log:
        filename = os.path.join(SCRIPT_DIR, f"bumps_pi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(filename, 'w') as f:
            json.dump(bumps_log, f, indent=2)
        print(f"  Saved to: {filename}")

    print("=" * 60)
    print("  Done!")


if __name__ == "__main__":
    main()
