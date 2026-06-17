#!/usr/bin/env python3
"""
Bump Detection API Server (Production)
Run this before starting detection.

Features:
- Spatial deduplication: bumps within 8m are merged as one
- Reports counter: tracks how many times a bump was reported
- reported_by: tracks unique device IDs that confirmed each bump
- min_confirmations filter for reliable bump queries
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import json
import os
import math
import tempfile
import threading
import uvicorn

# ==================== CONFIG ====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUMPS_FILE = os.path.join(SCRIPT_DIR, "bumps_data.json")

# FastAPI runs sync endpoints in a threadpool, so concurrent requests can hit the
# JSON file at the same time. This lock serialises the read-modify-write sections
# (writers) to prevent lost updates / duplicate bumps from a race.
_write_lock = threading.Lock()

# Deduplication: two bumps within this distance (meters) are treated as the same bump
# NEO-6M GPS accuracy is ~2.5-5m, so 8m catches GPS jitter
# while still allowing distinct bumps 10m+ apart
DEDUP_RADIUS_METERS = 8

# ==================== DATA MODELS ====================
class BumpReport(BaseModel):
    latitude: float
    longitude: float
    confidence: float
    timestamp: Optional[str] = None
    altitude: Optional[float] = None
    device_id: Optional[str] = None


# ==================== GEO UTILS ====================
def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two GPS coordinates using Haversine formula."""
    R = 6371000  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def find_nearby_bump(bumps, latitude, longitude, radius_m=DEDUP_RADIUS_METERS):
    """Find an existing bump within radius_m meters of the given coordinates.
    Returns (index, bump) or (None, None) if no nearby bump found."""
    for i, bump in enumerate(bumps):
        dist = haversine_distance(latitude, longitude, bump["latitude"], bump["longitude"])
        if dist <= radius_m:
            return i, bump
    return None, None


# ==================== APP ====================
app = FastAPI(title="Bump Detection API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== STORAGE ====================
def load_bumps():
    if not os.path.exists(BUMPS_FILE):
        return []
    try:
        with open(BUMPS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_bumps(bumps):
    """Atomically write bumps to disk: write to a temp file then os.replace().
    os.replace is atomic on POSIX, so a concurrent reader never sees a
    half-written (corrupt) file."""
    try:
        dir_name = os.path.dirname(BUMPS_FILE) or "."
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(bumps, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, BUMPS_FILE)
        finally:
            # Only present if os.replace failed before renaming it away.
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        return True
    except (IOError, OSError):
        return False


# ==================== ENDPOINTS ====================
@app.get("/")
def root():
    bumps = load_bumps()
    return {
        "service": "Bump Detection API",
        "version": "3.0",
        "total_bumps": len(bumps),
        "dedup_radius_m": DEDUP_RADIUS_METERS,
        "status": "running"
    }


@app.post("/report_bump")
def report_bump(bump: BumpReport):
    """Report a bump detection. If a bump already exists within DEDUP_RADIUS_METERS,
    it will be updated (confidence increased, reports_count incremented) instead of
    creating a duplicate."""
    timestamp = bump.timestamp or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    # Hold the lock across the whole load->check->modify->save so two concurrent
    # reports can't both "not find" each other and create duplicates.
    with _write_lock:
        bumps = load_bumps()

        # Check for nearby existing bump (deduplication)
        idx, existing = find_nearby_bump(bumps, bump.latitude, bump.longitude)

        if existing is not None:
            # Merge: update existing bump
            existing["reports_count"] = existing.get("reports_count", 1) + 1
            existing["confidence"] = round(
                max(existing["confidence"], bump.confidence), 4
            )
            existing["last_seen"] = timestamp

            # Track unique devices
            reporters = set(existing.get("reported_by", []))
            if bump.device_id:
                reporters.add(bump.device_id)
            existing["reported_by"] = sorted(reporters)

            bumps[idx] = existing

            if save_bumps(bumps):
                return {
                    "status": "merged",
                    "bump_id": existing["id"],
                    "reports_count": existing["reports_count"],
                    "message": f"Bump already known — updated (now {existing['reports_count']} reports)"
                }
            return {"status": "error", "message": "Failed to save"}

        # New unique bump
        bump_id = f"bump_{len(bumps):04d}"
        bump_data = {
            "id": bump_id,
            "latitude": bump.latitude,
            "longitude": bump.longitude,
            "confidence": round(bump.confidence, 4),
            "timestamp": timestamp,
            "last_seen": timestamp,
            "reports_count": 1,
            "reported_by": [bump.device_id] if bump.device_id else [],
        }
        if bump.altitude is not None:
            bump_data["altitude"] = bump.altitude

        bumps.append(bump_data)

        if save_bumps(bumps):
            return {"status": "success", "bump_id": bump_id, "reports_count": 1}
        return {"status": "error", "message": "Failed to save"}


@app.get("/get_bumps")
def get_bumps(limit: int = 100, min_confirmations: int = 1):
    """
    Get bumps, optionally filtered by minimum number of unique devices
    that have confirmed each bump.

    Args:
        limit: max number of bumps to return
        min_confirmations: only return bumps where len(reported_by) >= this value.
                          Default 1 includes everything (current behavior).
    """
    bumps = load_bumps()

    if min_confirmations > 1:
        bumps = [
            b for b in bumps
            if len(b.get("reported_by", [])) >= min_confirmations
        ]

    return {
        "total": len(bumps),
        "min_confirmations": min_confirmations,
        "bumps": bumps[-limit:] if len(bumps) > limit else bumps
    }


@app.delete("/clear_bumps")
def clear_bumps():
    with _write_lock:
        if save_bumps([]):
            return {"status": "success", "message": "All bumps cleared"}
    return {"status": "error", "message": "Failed to clear"}


# ==================== SERVER LAUNCH ====================
def start_server(host="0.0.0.0", port=8000, background=False):
    """Start the API server.
    - background=False: blocks and runs uvicorn (used by `python api_server.py`).
    - background=True:  runs uvicorn in a daemon thread and returns the thread
                        (used by run_laptop.py, which hosts the API in-process)."""
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    if background:
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        return thread
    server.run()
    return None


# ==================== MAIN ====================
if __name__ == "__main__":
    print("=" * 50)
    print("  Bump Detection API Server v3.0")
    print("=" * 50)
    print(f"  URL:  http://0.0.0.0:8000")
    print(f"  Data: {BUMPS_FILE}")
    print(f"  Dedup radius: {DEDUP_RADIUS_METERS}m")
    print("=" * 50)
    start_server(host="0.0.0.0", port=8000)
