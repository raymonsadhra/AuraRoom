"""
AuraRoom room-state classifier.

What this module does:
- Routes between ML-based anomaly detection and rules-based fallback logic to
  map room signals into a room state.

How it contributes to AuraRoom:
- Converts raw sensor signals into human-readable ambient intelligence labels
  that the dashboard can explain in the product story.

Hardware interaction:
- Indirect. Consumes outputs from camera/mic services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import math
from pathlib import Path
from typing import Any

try:
    import joblib
except Exception:  # pragma: no cover - runtime dependency
    joblib = None  # type: ignore


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RoomClassifier:
    """Room classifier with a strict ML kill switch.

    The app should always remain functional during demos. ML is opt-in through
    config, and every ML path is wrapped in a graceful fallback to the original
    deterministic rules.
    """

    use_ml_anomaly: bool = True
    model_path: str = "data/room_anomaly_model.pkl"
    motion_discussion_threshold: float = 0.045
    motion_chaotic_threshold: float = 0.10
    audio_discussion_threshold: float = 0.02
    audio_chaotic_threshold: float = 0.08
    _model: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            self._load_model()
        except Exception as exc:  # pragma: no cover - safety net
            LOGGER.warning("Anomaly model initialization failed; rules fallback will be used: %s", exc)
            self._model = None

    def _load_model(self) -> None:
        if not self.use_ml_anomaly:
            return
        if joblib is None:
            raise RuntimeError("joblib is unavailable")

        model_file = Path(self.model_path)
        if not model_file.exists():
            raise FileNotFoundError(f"anomaly model missing at {model_file}")

        self._model = joblib.load(model_file)
        LOGGER.info("Loaded anomaly model from %s", model_file)

    def classify(
        self,
        *,
        people_count: int,
        motion_level: float,
        audio_energy: float,
        hour: int,
    ) -> str:
        if not self.use_ml_anomaly:
            return self._classify_rules_based(
                people_count=people_count,
                motion_level=motion_level,
                audio_energy=audio_energy,
                hour=hour,
            )

        try:
            return self._classify_ml_based(
                people_count=people_count,
                motion_level=motion_level,
                audio_energy=audio_energy,
                hour=hour,
            )
        except Exception as exc:
            LOGGER.warning("ML classifier failed; falling back to rules-based logic: %s", exc)
            return self._classify_rules_based(
                people_count=people_count,
                motion_level=motion_level,
                audio_energy=audio_energy,
                hour=hour,
            )

    def _classify_rules_based(
        self,
        *,
        people_count: int,
        motion_level: float,
        audio_energy: float,
        hour: int,
    ) -> str:
        # No people detected -> room is effectively idle.
        if people_count <= 0:
            return "empty"

        # High movement + high noise implies chaotic collaborative activity.
        if motion_level >= self.motion_chaotic_threshold and audio_energy >= self.audio_chaotic_threshold:
            return "chaotic"

        # Moderate movement/noise with people usually signals discussion.
        if motion_level >= self.motion_discussion_threshold or audio_energy >= self.audio_discussion_threshold:
            return "discussion"

        # Quiet + low motion + occupied implies focused work.
        # Time-of-day can be used for lightweight biasing.
        if 9 <= hour <= 12 and audio_energy < self.audio_discussion_threshold:
            return "focused"
        if 13 <= hour <= 17 and motion_level < self.motion_discussion_threshold:
            return "focused"

        return "focused"

    def _classify_ml_based(
        self,
        *,
        people_count: int,
        motion_level: float,
        audio_energy: float,
        hour: int,
    ) -> str:
        if self._model is None:
            raise RuntimeError("anomaly model is not loaded")

        audio_level = self._to_audio_level(audio_energy)
        prediction = int(self._model.predict([[float(people_count), float(audio_level)]])[0])

        if prediction == -1:
            return self._classify_anomaly(people_count=people_count, audio_level=audio_level)

        return self._classify_rules_based(
            people_count=people_count,
            motion_level=motion_level,
            audio_energy=audio_energy,
            hour=hour,
        )

    def _classify_anomaly(self, *, people_count: int, audio_level: float) -> str:
        if people_count >= 40:
            return "crowd surge detected"
        if audio_level >= 82.0:
            return "unusually loud"
        if people_count <= 3 or audio_level <= 40.0:
            return "unusually quiet"
        return "anomalous room activity"

    def _to_audio_level(self, audio_energy: float) -> float:
        # Convert normalized RMS into a dB-like feature space that matches the
        # synthetic training data distribution used by the Isolation Forest.
        normalized = max(float(audio_energy), 0.000025)
        return 20.0 * math.log10(normalized / 0.000025)
