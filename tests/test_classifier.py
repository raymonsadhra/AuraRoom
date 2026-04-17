"""Basic classifier behavior checks for AuraRoom rule logic."""

from app.services.classifier_service import RoomClassifier


def test_empty_when_no_people() -> None:
    classifier = RoomClassifier()
    state = classifier.classify(people_count=0, motion_level=0.2, audio_energy=0.2, hour=10)
    assert state == "empty"


def test_chaotic_when_high_motion_and_audio() -> None:
    classifier = RoomClassifier()
    state = classifier.classify(people_count=4, motion_level=0.2, audio_energy=0.2, hour=15)
    assert state == "chaotic"


def test_discussion_when_audio_medium() -> None:
    classifier = RoomClassifier()
    state = classifier.classify(people_count=3, motion_level=0.01, audio_energy=0.03, hour=11)
    assert state == "discussion"


def test_rules_used_when_ml_kill_switch_disabled() -> None:
    classifier = RoomClassifier(use_ml_anomaly=False)
    state = classifier.classify(people_count=2, motion_level=0.0, audio_energy=0.0, hour=14)
    assert state == "focused"


def test_missing_model_falls_back_to_rules() -> None:
    classifier = RoomClassifier(use_ml_anomaly=True, model_path="data/does_not_exist.pkl")
    state = classifier.classify(people_count=4, motion_level=0.01, audio_energy=0.03, hour=11)
    assert state == "discussion"


class _StubModel:
    def __init__(self, prediction: int) -> None:
        self.prediction = prediction

    def predict(self, _features: list[list[float]]) -> list[int]:
        return [self.prediction]


def test_ml_anomaly_path_returns_descriptive_state() -> None:
    classifier = RoomClassifier(use_ml_anomaly=False)
    classifier.use_ml_anomaly = True
    classifier._model = _StubModel(-1)

    state = classifier.classify(people_count=55, motion_level=0.02, audio_energy=0.04, hour=16)
    assert state == "crowd surge detected"
