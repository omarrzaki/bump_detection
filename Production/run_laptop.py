#!/usr/bin/env python3
"""
LAPTOP TESTING VERSION - Bump Detection with Mock GPS + API
============================================================
This is the TESTING version for your laptop.
Uses simulated GPS data (no hardware needed).
Includes API server for mobile app testing.

To run: python Production/run_laptop.py
API will be on: http://localhost:8000
"""

from ultralytics import YOLO
import cv2
import os
import time
from datetime import datetime, timezone
import random
import requests

# Import shared API server
try:
    from api_server import start_server
    API_AVAILABLE = True
except ImportError:
    print("Warning: api_server.py not found - running without API")
    API_AVAILABLE = False

# ==================== CONFIGURATION ====================
# Use the original training-weights path if it exists on this machine, otherwise
# fall back to a model bundled next to this script (portable across laptops).
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_LEGACY_MODEL = "/home/omar/Reposetry/BumpDetection/runs/detect/train/weights/best.pt"
MODEL_PATH = _LEGACY_MODEL if os.path.exists(_LEGACY_MODEL) else next(
    (os.path.join(SCRIPT_DIR, n)
     for n in ("best_yolo11.pt", "best.pt")
     if os.path.exists(os.path.join(SCRIPT_DIR, n))),
    os.path.join(SCRIPT_DIR, "best.pt"),
)
CONFIDENCE_THRESHOLD = 0.5
PROCESS_EVERY_N_FRAMES = 2
BUMP_COOLDOWN_SECONDS = 3

# API settings
API_URL = "http://localhost:8000"

# Mock GPS settings (simulated location - Cairo)
BASE_LATITUDE = 30.0444
BASE_LONGITUDE = 31.2357

# ==================== MOCK GPS CLASS ====================
class MockGPS:
    """Simulates GPS for laptop testing"""
    def __init__(self, lat, lng):
        self.base_lat = lat
        self.base_lng = lng
    
    def get_location(self):
        """Returns simulated GPS coordinates with small random movement"""
        return {
            'latitude': self.base_lat + random.uniform(-0.0001, 0.0001),
            'longitude': self.base_lng + random.uniform(-0.0001, 0.0001),
            'altitude': 45.6,
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }

# ====================REPORT TO API ====================
def report_to_api(location, confidence):
    """Report bump to API server"""
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
    except:
        return False


# ==================== MAIN PROGRAM ====================
def main():
    print("="*70)
    print("BUMP DETECTION - LAPTOP TESTING MODE")
    print("="*70)
    print("Using SIMULATED GPS data (Mock GPS)")
    
    # Start API server in background
    if API_AVAILABLE:
        print("Starting API server on http://localhost:8000 ...")
        start_server(host="0.0.0.0", port=8000, background=True)
        time.sleep(2)  # Wait for server to start
        print("✓ API server running")
    else:
        print("✗ API server not available")
    
    print("="*70)
    
    # Load YOLO model
    print(f"Loading model: {MODEL_PATH}")
    model = YOLO(MODEL_PATH)
    print("✓ Model loaded")
    
    # Initialize Mock GPS
    gps = MockGPS(BASE_LATITUDE, BASE_LONGITUDE)
    print(f"✓ Mock GPS initialized at {BASE_LATITUDE}, {BASE_LONGITUDE}")
    
    # Initialize camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("✗ Error: Could not open camera")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    print("✓ Camera ready")
    
    # Variables
    frame_counter = 0
    last_bump_time = 0
    bump_count = 0
    bumps_log = []
    
    # FPS tracking
    prev_time = time.time()
    fps = 0
    
    print()
    print("Controls:")
    print("  'q' - Quit")
    print("  's' - Save current location")
    print("="*70)
    print()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_counter += 1
        
        # Calculate FPS
        current_time = time.time()
        fps = 1.0 / (current_time - prev_time) if (current_time - prev_time) > 0 else 0
        prev_time = current_time
        
        # Process every N frames
        should_process = (frame_counter % PROCESS_EVERY_N_FRAMES == 0)
        
        if should_process:
            # Run YOLO detection
            results = model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)
            annotated_frame = results[0].plot()
            
            # Check for bumps
            if len(results[0].boxes) > 0:
                # Extract highest confidence
                highest_conf = max(float(box.conf[0]) for box in results[0].boxes)
                
                # Bump detected!
                if time.time() - last_bump_time > BUMP_COOLDOWN_SECONDS:
                    # Get GPS location
                    location = gps.get_location()
                    
                    # Log bump
                    bump_data = {
                        'id': f"bump_{bump_count}",
                        'latitude': location['latitude'],
                        'longitude': location['longitude'],
                        'timestamp': location['timestamp'],
                        'confidence': highest_conf
                    }
                    bumps_log.append(bump_data)
                    bump_count += 1
                    last_bump_time = time.time()
                    
                    # Report to API
                    api_sent = False
                    if API_AVAILABLE:
                        api_sent = report_to_api(location, highest_conf)
                    api_status = "✓ API" if api_sent else "✗ API"
                    
                    # Print to console
                    print(f"🚧 BUMP #{bump_count} detected! {api_status}")
                    print(f"   Location: {location['latitude']:.6f}, {location['longitude']:.6f}")
                    print(f"   Time: {location['timestamp']}")
                    print(f"   Maps: https://www.google.com/maps?q={location['latitude']},{location['longitude']}")
                    print()
        else:
            annotated_frame = frame
        
        # Get current location for display
        current_loc = gps.get_location()
        
        # Display info on frame
        cv2.putText(annotated_frame, f"FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(annotated_frame, f"GPS (MOCK): {current_loc['latitude']:.6f}, {current_loc['longitude']:.6f}",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2)
        cv2.putText(annotated_frame, f"Bumps: {bump_count}", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(annotated_frame, "TESTING MODE", (10, 450),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        
        # Show frame
        cv2.imshow("Bump Detection - Laptop Testing (Press 'q' to quit)", annotated_frame)
        
        # Handle keyboard
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            loc = gps.get_location()
            print(f"📍 Manual save: {loc['latitude']:.6f}, {loc['longitude']:.6f}")
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    
    # Summary
    print()
    print("="*70)
    print("SESSION SUMMARY")
    print("="*70)
    print(f"Total bumps detected: {bump_count}")
    
    if bumps_log:
        # Save to file
        import json
        filename = f"bumps_laptop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(bumps_log, f, indent=2)
        print(f"✓ Saved to: {filename}")
    
    print("Done!")

if __name__ == "__main__":
    main()
