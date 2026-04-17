"""
AuraRoom detection service.

What this module does:
- Wraps YOLO person detection behind a small interface.

How it contributes to AuraRoom:
- Isolates model loading/inference so camera capture logic stays responsive.

Hardware interaction:
- Indirect. Consumes camera frames, but does not open camera hardware itself.
"""

from __future__ import annotations

import logging
from typing import Any


LOGGER = logging.getLogger(__name__)

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover
    YOLO = None  # type: ignore


class YOLOPersonDetector:
    def __init__(self, *, model_name: str, conf_threshold: float) -> None:
        self.model_name = model_name
        self.conf_threshold = conf_threshold
        self._model: Any = None

        if YOLO is None:
            LOGGER.warning("ultralytics not available; person detection disabled")
            return

        try:
            # Lightweight model keeps Pi-friendly inference latency.
            self._model = YOLO(model_name)
        except Exception as exc:
            LOGGER.warning("Could not load YOLO model %s: %s", model_name, exc)

    @property
    def available(self) -> bool:
        return self._model is not None

    def detect_people_count(self, frame: Any) -> int:
        if self._model is None:
            return 0

        try:
            results = self._model.predict(frame, conf=self.conf_threshold, verbose=False)
            if not results:
                return 0
            boxes = results[0].boxes
            if boxes is None:
                return 0
            return sum(1 for cls_id in boxes.cls.tolist() if int(cls_id) == 0)
        except Exception as exc:
            LOGGER.debug("Person detection failed: %s", exc)
            return 0
