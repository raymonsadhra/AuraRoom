"""
AuraRoom camera and vision pipeline.

What this module does:
- Opens a webcam/Pi camera, reads frames continuously, estimates motion level,
  and runs YOLO person detection on a throttled interval.

How it contributes to AuraRoom:
- Provides two core room signals: how many people are visible and how active
  movement is. These are core inputs for state classification.

Hardware interaction:
- Direct. This module talks to camera hardware through OpenCV VideoCapture.
- Includes Raspberry Pi-aware throttling to keep inference lightweight.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover - depends on runtime availability
    cv2 = None  # type: ignore

from app.services.detection_service import YOLOPersonDetector


LOGGER = logging.getLogger(__name__)


class CameraService:
    def __init__(
        self,
        *,
        enabled: bool,
        camera_index: int,
        width: int,
        height: int,
        fps: int,
        fourcc: str,
        use_v4l2: bool,
        yolo_model_name: str,
        conf_threshold: float,
        infer_every_n_frames: int,
    ) -> None:
        self.enabled = enabled
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.fourcc = fourcc
        self.use_v4l2 = use_v4l2
        self.conf_threshold = conf_threshold
        self.infer_every_n_frames = max(1, infer_every_n_frames)

        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._capture: Any = None
        self._detector: YOLOPersonDetector | None = None

        self._people_count = 0
        self._motion_level = 0.0
        self._last_frame_ts = 0.0
        self._frame_index = 0
        self._prev_gray: np.ndarray | None = None

        if self.enabled:
            # YOLOv8n is intentionally lightweight so Raspberry Pi CPU-only
            # inference remains usable for a live demo.
            self._detector = YOLOPersonDetector(
                model_name=yolo_model_name,
                conf_threshold=conf_threshold,
            )
            if self._detector.available:
                LOGGER.info("Loaded YOLO detector: %s", yolo_model_name)
            else:
                LOGGER.warning("YOLO detector unavailable; people_count will stay conservative")

    def start(self) -> None:
        if not self.enabled:
            LOGGER.warning("Camera service disabled by config")
            return
        if cv2 is None:
            LOGGER.warning("OpenCV not available; camera service disabled")
            return
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="camera-service", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "people_count": self._people_count,
                "motion_level": round(self._motion_level, 4),
                "camera_last_frame_ts": self._last_frame_ts,
            }

    def _run_loop(self) -> None:
        try:
            # For Linux/Raspberry Pi with USB UVC cameras, CAP_V4L2 is usually
            # the most stable backend. We keep fallback behavior if unsupported.
            if self.use_v4l2 and hasattr(cv2, "CAP_V4L2"):
                self._capture = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
            else:
                self._capture = cv2.VideoCapture(self.camera_index)
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._capture.set(cv2.CAP_PROP_FPS, self.fps)
            if self.fourcc:
                fourcc = cv2.VideoWriter_fourcc(*self.fourcc[:4])
                self._capture.set(cv2.CAP_PROP_FOURCC, fourcc)
        except Exception as exc:
            LOGGER.error("Could not initialize camera device %s: %s", self.camera_index, exc)
            return

        if not self._capture or not self._capture.isOpened():
            LOGGER.error("Camera device %s is not available", self.camera_index)
            return

        LOGGER.info("Camera service started on index %s", self.camera_index)
        while not self._stop_event.is_set():
            ok, frame = self._capture.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue

            self._frame_index += 1
            motion_level = self._compute_motion(frame)
            people_count = self._people_count

            # Throttle object detection to reduce CPU load and keep loop stable.
            if self._detector is not None and self._frame_index % self.infer_every_n_frames == 0:
                people_count = self._detect_people(frame)

            with self._lock:
                self._motion_level = motion_level
                self._people_count = people_count
                self._last_frame_ts = time.time()

            # Small sleep prevents the loop from maxing CPU when camera is fast.
            time.sleep(0.01)

        LOGGER.info("Camera service stopped")

    def _compute_motion(self, frame: np.ndarray) -> float:
        if cv2 is None:
            return 0.0

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self._prev_gray is None:
            self._prev_gray = gray
            return 0.0

        diff = cv2.absdiff(self._prev_gray, gray)
        self._prev_gray = gray

        # Normalize average pixel delta to 0..1 for easier thresholding.
        mean_delta = float(np.mean(diff))
        motion_level = min(1.0, mean_delta / 255.0)
        return motion_level

    def _detect_people(self, frame: np.ndarray) -> int:
        if self._detector is None:
            return self._people_count

        try:
            # Resize to lighten inference. Lower resolution is usually enough for
            # person count trends in a hackathon room demo.
            return self._detector.detect_people_count(frame)
        except Exception as exc:
            LOGGER.debug("YOLO inference failure: %s", exc)
            return self._people_count
