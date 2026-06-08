#!/usr/bin/env python3
"""
Bump Detection API Server (Production)
Run this before starting detection.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import json
import os
import uvicorn

# ==================== CONFIG ====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUMPS_FILE = os.path.join(SCRIPT_DIR, "bumps_data.json")

# ==================== DATA MODELS ====================
class BumpReport(BaseModel):
    latitude: float
    longitude: float
    confidence: float
    timestamp: Optional[str] = None
    altitude: Optional[float] = None


# ==================== APP ====================
app = FastAPI(title="Bump Detection API", version="2.0")

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
    try:
        with open(BUMPS_FILE, 'w') as f:
            json.dump(bumps, f, indent=2)
        return True
    except IOError:
        return False


# ==================== ENDPOINTS ====================
@app.get("/")
def root():
    bumps = load_bumps()
    return {
        "service": "Bump Detection API",
        "version": "2.0",
        "total_bumps": len(bumps),
        "status": "running"
    }


@app.post("/report_bump")
def report_bump(bump: BumpReport):
    bumps = load_bumps()
    bump_id = f"bump_{len(bumps)}"
    timestamp = bump.timestamp or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    bump_data = {
        "id": bump_id,
        "latitude": bump.latitude,
        "longitude": bump.longitude,
        "confidence": bump.confidence,
        "timestamp": timestamp,
    }
    if bump.altitude is not None:
        bump_data["altitude"] = bump.altitude

    bumps.append(bump_data)

    if save_bumps(bumps):
        return {"status": "success", "bump_id": bump_id}
    return {"status": "error", "message": "Failed to save"}


@app.get("/get_bumps")
def get_bumps(limit: int = 100):
    bumps = load_bumps()
    return {
        "total": len(bumps),
        "bumps": bumps[-limit:] if len(bumps) > limit else bumps
    }


@app.delete("/clear_bumps")
def clear_bumps():
    if save_bumps([]):
        return {"status": "success", "message": "All bumps cleared"}
    return {"status": "error", "message": "Failed to clear"}


# ==================== MAIN ====================
if __name__ == "__main__":
    print("=" * 50)
    print("  Bump Detection API Server v2.0")
    print("=" * 50)
    print(f"  URL:  http://0.0.0.0:8000")
    print(f"  Data: {BUMPS_FILE}")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
