"""
Quick camera sanity check for AuraRoom hardware setup.

What this script does:
- Opens webcam feed and displays live motion estimate and people count.

How it contributes to AuraRoom:
- Lets the team verify camera angle/device access before running full stack.

Hardware interaction:
- Direct camera access via OpenCV and optional YOLO detection.
"""

from __future__ import annotations

import time
from pathlib import Path
import sys

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import load_config
from app.services.camera_service import CameraService


def main() -> None:
    if cv2 is None:
        print("OpenCV is not installed. Run: pip install -r requirements-sensors.txt")
        return

    cfg = load_config()
    service = CameraService(
        enabled=True,
        camera_index=cfg.camera_index,
        width=cfg.camera_width,
        height=cfg.camera_height,
        fps=cfg.camera_fps,
        fourcc=cfg.camera_fourcc,
        use_v4l2=cfg.camera_use_v4l2,
        yolo_model_name=cfg.yolo_model_name,
        conf_threshold=cfg.yolo_conf_threshold,
        infer_every_n_frames=cfg.yolo_infer_every_n_frames,
    )
    service.start()

    print("Camera test running. Press Ctrl+C to stop.")
    try:
        while True:
            metrics = service.get_metrics()
            print(metrics)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()


if __name__ == "__main__":
    main()
