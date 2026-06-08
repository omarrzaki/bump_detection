# Production Files - Setup Instructions

## Quick Start

### 1. On Laptop (Testing):
```bash
# Start API server (Terminal 1)
python Production/api_server.py

# Start detection (Terminal 2)  
python Production/run_laptop.py
```

### 2. On Raspberry Pi (Production):
```bash
# Step 1: Update API_URL in run_raspberry_pi.py
# Get Pi IP:
hostname -I
# Edit line 31: API_URL = "http://YOUR_PI_IP:8000"

# Step 2: Start API server (Terminal 1 or screen/tmux)
python Production/api_server.py

# Step 3: Start detection (Terminal 2)
python Production/run_raspberry_pi.py
```

## Files:

- **api_server.py** - FastAPI server (run separately)
- **run_laptop.py** - Testing version (mock GPS)
- **run_raspberry_pi.py** - Production version (real GPS)

## Configuration (run_raspberry_pi.py):

```python
PROCESS_EVERY_N_FRAMES = 4    # Processing frequency
ENABLE_DISPLAY = False        # Headless mode
API_URL = "http://192.168.1.50:8000"  # UPDATE THIS!
```

## Mobile App Connection:

```
GET http://PI_IP:8000/get_bumps
```

## Recent Fixes (v1.1):

✅ Fixed highest_conf undefined bug
✅ API server runs separately (not in same process)
✅ Added headless mode flag
✅ Reduced Pi load (PROCESS_EVERY_N_FRAMES = 4)
✅ API_URL uses network IP (not localhost)
