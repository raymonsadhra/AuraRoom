# AuraRoom Hardware Notes

## Current MVP Hardware Assumptions
- Raspberry Pi 4 or laptop can run Python 3.10+.
- Camera: USB 2.0 UVC Camera Board 1080P Day&Night Vision Automatic IR-Cut.
- Microphone: MEMS microphone (ESD/EMI-protected, plug-and-play).
- One camera is available as OpenCV device index `0` by default.
- One microphone is available as the default input device for `sounddevice` (or set `AUDIO_DEVICE_INDEX`).
- YOLO inference uses `yolov8n.pt` because heavier models can cause frame lag on Pi CPU-only setups.

## Recommended Config For This Camera/Mic
- `CAMERA_INDEX=0`
- `CAMERA_WIDTH=640`
- `CAMERA_HEIGHT=480`
- `CAMERA_FPS=30`
- `CAMERA_FOURCC=MJPG`
- `CAMERA_USE_V4L2=true` (Linux/Raspberry Pi)
- `AUDIO_DEVICE_INDEX=-1` (default input)
- `AUDIO_SAMPLERATE=16000`

## Placement Guidance
- Camera should be mounted to capture a broad room view; avoid backlight facing windows.
- Microphone should be near room center and away from fan vents for cleaner energy signals.

## Reliability Guidance for Long-Running Demo
- Keep the Pi powered with a stable supply.
- Use active cooling if continuous YOLO inference is enabled.
- Reduce `YOLO_INFER_EVERY_N_FRAMES` frequency if CPU gets saturated.

## Planned Sensor Extensions
- GPIO PIR sensor:
  - Add `pir_service.py` to read digital motion events.
  - Fuse PIR events with frame differencing for low-light robustness.
- BME680 sensor:
  - Add `env_service.py` for temperature/humidity/air quality.
  - Extend snapshot schema with environmental fields for comfort analytics.
- OLED/e-ink display:
  - Add `display_service.py` to show current room state and health locally.

## Suggested Integration Points
- `app/orchestrator.py`:
  - Inject new sensor services and include outputs in each `RoomSnapshot`.
- `app/services/classifier_service.py`:
  - Extend rule conditions with new environmental and PIR features.
- `static/app.js`:
  - Add new cards/charts for comfort and occupancy confidence.
