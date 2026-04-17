# AuraRoom

AuraRoom is a hackathon-ready ambient intelligence system that reads a room with camera + microphone signals and converts them into live room-state insights.

## 1. Architecture Summary

AuraRoom uses a 3-layer pipeline:

1. Perception Layer:
- `CameraService` captures video frames, estimates motion, and runs YOLO person detection.
- `AudioService` captures microphone audio and computes smoothed energy/noise level.

2. Interpretation Layer:
- `RoomClassifier` maps people + motion + audio + time into `empty`, `focused`, `discussion`, or `chaotic`.
- `InsightService` creates natural language insights using local templates or optional LLM mode.

3. Visualization Layer:
- Flask API exposes current metrics, history, insights, and health.
- Dashboard (`static/`) polls APIs and renders cards + charts.

## 2. Repository Structure

```text
auraroom/
  app/
    api/
      routes.py
    models/
      snapshot.py
    services/
      audio_service.py
      camera_service.py
      classifier_service.py
      detection_service.py
      insight_service.py
      logger_service.py
    config.py
    main.py
    orchestrator.py
    state.py
  data/
  docs/
    hardware_notes.md
  scripts/
    test_audio.py
    test_camera.py
  static/
    app.js
    index.html
    style.css
  tests/
    test_classifier.py
  .env.example
  main.py
  requirements.txt
  README.md
```

## 3. Hardware Setup

Recommended:
- Raspberry Pi 4
- USB 2.0 UVC Camera Board 1080P Day&Night Vision Automatic IR-Cut
- MEMS microphone (ESD/EMI-protected, plug-and-play)
- Reliable 5V power supply

Placement:
- Camera with wide room view.
- Mic near room center.

More details: `docs/hardware_notes.md`.

For your camera + mic combo, start with these defaults in `.env`:
- `CAMERA_INDEX=0`
- `CAMERA_WIDTH=640`
- `CAMERA_HEIGHT=480`
- `CAMERA_FPS=30`
- `CAMERA_FOURCC=MJPG`
- `CAMERA_USE_V4L2=true` (recommended on Linux/Raspberry Pi)
- `AUDIO_DEVICE_INDEX=-1` (use default mic)

## 4. Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

This installs the core app so you can run dashboard + backend now, even without camera/mic hardware.

### Optional full sensor stack (camera + YOLO + mic)

```bash
pip install -r requirements-sensors.txt
```

Notes:
- On macOS with Python 3.13+, some vision/audio dependencies may not resolve cleanly.
- For the most reliable full sensor setup, use Python 3.11.

## 5. Run AuraRoom

```bash
python main.py
```

Backend runs on `http://localhost:8000` by default.
Dashboard:
- `http://localhost:8000/`
- or `http://localhost:8000/dashboard`

## 6. API Endpoints

- `GET /api/current` - latest room snapshot
- `GET /api/history` - recent events + hourly summary
- `GET /api/insights` - latest insight + recent tail
- `GET /api/health` - service health

## 7. Sensor Sanity Tests

List available camera/mic device indexes first:

```bash
python scripts/list_devices.py
```

Test camera pipeline:

```bash
python scripts/test_camera.py
```

Test microphone pipeline:

```bash
python scripts/test_audio.py
```

If OpenCV or sounddevice are not installed yet, these scripts will indicate what to install.

## 8. Insight Modes

### Local Mode (default)
- No cloud dependency.
- Best for demo reliability.

Set in `.env`:

```env
INSIGHT_MODE=local
```

### LLM Mode (optional)
- Requires API key.
- Automatically falls back to local templates if the LLM call fails.

Set in `.env`:

```env
INSIGHT_MODE=llm
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

## 9. Logging and History

Default logging backend is JSONL (`data/room_events.jsonl`) for maximum portability.

To use SQLite:

```env
LOG_BACKEND=sqlite
LOG_PATH_SQLITE=data/room_events.db
```

Each event stores timestamp, people count, motion, audio, noise label, room state, and insight text.

## 10. Raspberry Pi Notes

- `yolov8n.pt` is used because it is lightweight enough for edge inference.
- Increase `YOLO_INFER_EVERY_N_FRAMES` for lower CPU usage.
- Keep active cooling for continuous demo sessions.
- If your UVC camera stream is unstable, keep `CAMERA_USE_V4L2=true` and `CAMERA_FOURCC=MJPG`.

## 11. Future Extensions

- GPIO PIR sensor for binary motion confidence.
- BME680 for environmental context.
- OLED/e-ink side display for local room-state display.
- Replace rule-based classifier with learned model after collecting labeled logs.

## 12. Running Tests

```bash
pytest -q
```
