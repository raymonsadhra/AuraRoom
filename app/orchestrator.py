"""
AuraRoom runtime orchestrator.

What this module does:
- Starts/stops sensor services, runs periodic aggregation/classification,
  triggers insights, and persists snapshots.

How it contributes to AuraRoom:
- Connects perception, interpretation, and visualization layers into one live
  loop that powers the demo dashboard.

Hardware interaction:
- Indirect coordinator. Starts hardware-facing camera/audio services and merges
  their outputs.
"""

from __future__ import annotations

from datetime import datetime
import logging
import threading
import time
from typing import Any

from app.config import AppConfig
from app.models.snapshot import RoomSnapshot
from app.services.audio_service import AudioService
from app.services.camera_service import CameraService
from app.services.classifier_service import RoomClassifier
from app.services.insight_service import InsightService
from app.services.logger_service import LoggerService
from app.state import AppState


LOGGER = logging.getLogger(__name__)


class AuraOrchestrator:
    def __init__(self, *, config: AppConfig, state: AppState, logger_service: LoggerService) -> None:
        self.config = config
        self.state = state
        self.logger_service = logger_service

        self.camera_service = CameraService(
            enabled=config.vision_enabled,
            camera_index=config.camera_index,
            width=config.camera_width,
            height=config.camera_height,
            fps=config.camera_fps,
            fourcc=config.camera_fourcc,
            use_v4l2=config.camera_use_v4l2,
            yolo_model_name=config.yolo_model_name,
            conf_threshold=config.yolo_conf_threshold,
            infer_every_n_frames=config.yolo_infer_every_n_frames,
        )
        self.audio_service = AudioService(
            enabled=config.audio_enabled,
            samplerate=config.audio_samplerate,
            blocksize=config.audio_blocksize,
            device_index=config.audio_device_index,
            smoothing_alpha=config.audio_smoothing_alpha,
            noise_low_threshold=config.noise_low_threshold,
            noise_high_threshold=config.noise_high_threshold,
        )
        self.classifier = RoomClassifier()
        self.insight_service = InsightService.build(
            mode=config.insight_mode,
            llm_provider_name=config.llm_provider,
            openai_api_key=config.openai_api_key,
            openai_model=config.openai_model,
        )

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_insight_ts = 0.0

    def start(self) -> None:
        self.camera_service.start()
        self.audio_service.start()

        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="auraroom-orchestrator", daemon=True)
        self._thread.start()
        LOGGER.info("AuraOrchestrator started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=4)

        self.camera_service.stop()
        self.audio_service.stop()
        self.logger_service.close()
        LOGGER.info("AuraOrchestrator stopped")

    def _loop(self) -> None:
        interval = max(0.5, self.config.sample_interval_sec)

        while not self._stop_event.is_set():
            started = time.time()

            camera_metrics = self.camera_service.get_metrics()
            audio_metrics = self.audio_service.get_metrics()

            now = datetime.now()
            room_state = self.classifier.classify(
                people_count=int(camera_metrics.get("people_count", 0)),
                motion_level=float(camera_metrics.get("motion_level", 0.0)),
                audio_energy=float(audio_metrics.get("audio_energy", 0.0)),
                hour=now.hour,
            )

            snapshot = RoomSnapshot(
                timestamp=now.isoformat(timespec="seconds"),
                hour=now.hour,
                people_count=int(camera_metrics.get("people_count", 0)),
                motion_level=float(camera_metrics.get("motion_level", 0.0)),
                audio_energy=float(audio_metrics.get("audio_energy", 0.0)),
                noise_level_label=str(audio_metrics.get("noise_level_label", "low")),
                room_state=room_state,
                insight_text=self.state.get_latest_insight(),
            ).to_dict()

            self.state.update_current(snapshot)
            self.state.add_snapshot(snapshot)
            self.logger_service.log_snapshot(snapshot)

            # Insight generation runs less frequently than sensor sampling.
            now_ts = time.time()
            if now_ts - self._last_insight_ts >= max(5.0, self.config.insight_interval_sec):
                history = self.state.get_history(limit=300)
                insight = self.insight_service.generate(snapshot, history)
                self.state.set_latest_insight(insight)

                snapshot_with_insight = dict(snapshot)
                snapshot_with_insight["insight_text"] = insight
                self.state.update_current(snapshot_with_insight)
                self.logger_service.log_snapshot(snapshot_with_insight)
                self._last_insight_ts = now_ts

            elapsed = time.time() - started
            sleep_for = max(0.01, interval - elapsed)
            time.sleep(sleep_for)
