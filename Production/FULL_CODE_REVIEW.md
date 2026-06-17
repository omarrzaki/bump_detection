# Full Code Review Request — Bump Detection Project

> **To the AI agent:** Please perform a careful, complete review of the entire codebase. The user has a working system but discovered a color bug during a live camera test. While fixing it, audit all files thoroughly for related and unrelated issues. Read every file in full — don't skim. This is a graduation project with a defense coming up, so correctness and reliability matter more than cleverness.

---

## 🐛 Primary Bug: Camera Shows Blue Tint

### Symptom
During a live VNC test with `ENABLE_DISPLAY = True`, the camera preview shows the user's face with a **strong blue tint**. Skin tones appear blue, and what should be warm colors appear cold. This is the classic **RGB↔BGR channel swap**.

### Likely Root Cause
In `run_raspberry_pi.py`, the `PiCameraCapture` class configures picamera2 with `format="RGB888"` and then also runs:
```python
frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
```

The bug is almost certainly one of these:
1. **Double conversion** — picamera2 is already delivering BGR-compatible data, and the extra `cvtColor` swaps it again.
2. **Format mismatch** — picamera2's `RGB888` format in this libcamera version actually delivers channels in BGR order (this is a known quirk on some Pi OS / libcamera versions), so the explicit `RGB2BGR` conversion is what *creates* the swap.

### What to Investigate
- Check what channel order picamera2 actually returns on this setup (Pi 5, Trixie, libcamera v0.7.1).
- Determine whether YOLO inference and the saved/displayed frames need BGR (OpenCV convention) or RGB.
- **Important:** The fix must keep colors correct in BOTH:
  - The YOLO model input (so detection accuracy isn't affected)
  - The display window (`ENABLE_DISPLAY`) and any saved frames/video

### Suggested Approach
- Test removing the `cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)` line and observe.
- OR change the picamera2 format configuration.
- Verify YOLO detection still works after the change — the model was likely trained on RGB or BGR images; whichever it was, the inference input must match training. Do not fix the display at the expense of detection accuracy.
- Add a brief code comment explaining the final channel-order decision so it's not "fixed" incorrectly later.

---

## 🔍 Full Codebase Audit (read every file completely)

Please open and read each of these in full, then report issues found:

### `Production/run_raspberry_pi.py`
Check for:
- The color/channel bug above
- Whether the GPS validation (Egypt bounds) was implemented (it was requested earlier)
- Whether audio feedback was implemented (requested earlier)
- Whether device_id tracking was implemented (requested earlier)
- Error handling around camera/GPS disconnects mid-run
- The cooldown logic correctness
- Any resource leaks (camera/GPS not released on crash paths)
- Hardcoded paths that might break (`MODEL_PATH`, `API_URL`)

### `Production/api_server.py`
Check for:
- The haversine deduplication correctness
- Whether `min_confirmations` filter on `/get_bumps` was added (requested earlier)
- Whether `reported_by` / `device_id` handling was added (requested earlier)
- Thread-safety of the JSON read/write (concurrent requests could corrupt the file)
- Proper error responses
- Whether the data model matches what the mobile app will expect

### `Production/start.sh` and `Production/setup_pi.sh`
Check for:
- Trixie compatibility (`libcamera-*` → `rpicam-*` renames)
- PEP 668 handling (pip must run inside venv)
- Correct device paths (`/dev/ttyACM0` for the USB GPS, not `/dev/ttyAMA0`)
- Whether the scripts reference files/dirs that actually exist

### `requirements.txt`
Check for:
- Python 3.13 compatibility (Trixie ships 3.13)
- Whether `picamera2` is pip-installed (it should use the system package instead)
- Any missing dependencies actually used in the code (`pygame` if audio was added, etc.)
- Version pins that might conflict

### Any other files in the project
- Model weights location (`best.pt`) — is the path consistent across files?
- Any leftover laptop-testing code (`TestServer/`, `LiveCameraWithAPI/`) that might confuse the build

---

## 🌡️ Secondary Observation: High Temperature

During the test, `vcgencmd measure_temp` showed **77.9°C**. The user has an official Active Cooler to install (hardware fix, not code). No code change needed, but:
- Confirm there's no busy-wait or unnecessary CPU spin in the main loop that inflates temperature.
- The current `time.sleep(0.005)` in the headless path is fine; just verify the loop isn't processing every single frame when it shouldn't (it should respect `PROCESS_EVERY_N_FRAMES`).

---

## 🎯 Known Context (environment)

- **Hardware:** Raspberry Pi 5 (8GB) + Pi Camera Module v2 (imx219) + u-blox NEO-6M GPS via USB
- **OS:** Debian 13 Trixie (NOT Bookworm)
- **Python:** 3.13, running inside `bump_env` virtual environment
- **GPS device path:** `/dev/ttyACM0`
- **Camera:** accessed via `picamera2` (libcamera v0.7.1), 640x480, RGB888 configured
- **Inference:** Appears to be using NCNN export of the YOLO model (saw "model for NCNN inference" in logs) — verify this is intentional and the NCNN model matches the original `best.pt`
- **Display:** Currently testing with `ENABLE_DISPLAY = True` over VNC
- **Note on NCNN:** The logs show NCNN inference is being used. If the model was converted from `best.pt` to NCNN format, confirm the conversion preserved accuracy and that the color channel order expected by the NCNN model matches what the camera provides. This ties directly into the blue-tint bug — a channel swap could also be silently hurting detection accuracy.

---

## ✅ Deliverables

After your review, please provide:
1. The fix for the blue-tint color bug (with explanation of root cause)
2. A list of any other bugs or issues found, ranked by severity
3. Confirmation of which previously-requested features are present vs missing:
   - GPS Egypt-bounds validation
   - Audio feedback (success/warning beeps)
   - device_id tracking
   - min_confirmations filter
4. Any Trixie/Python 3.13 compatibility concerns
5. Whether the NCNN inference path is safe (matches the original model's accuracy and color expectations)

Do not make sweeping refactors. Fix what's broken, flag what's risky, and keep the working parts working. The defense is the priority — stability over elegance.
