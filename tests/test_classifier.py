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
