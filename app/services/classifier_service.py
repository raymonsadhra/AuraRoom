"""
AuraRoom room-state classifier.

What this module does:
- Maps people count, motion, audio, and time context to a room state.

How it contributes to AuraRoom:
- Converts raw sensor signals into human-readable ambient intelligence labels
  that the dashboard can explain in the product story.

Hardware interaction:
- Indirect. Consumes outputs from camera/mic services.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RoomClassifier:
    """Rule-based classifier for weekend MVP reliability.

    Rule-based logic is ideal for hackathons because:
    - it is transparent and easy to tune live,
    - no labeled dataset is required,
    - behavior is predictable under demo pressure.

    TODO: Replace with a learned classifier once sufficient labeled room-event
    data is collected from the logger service.
    """

    motion_discussion_threshold: float = 0.045
    motion_chaotic_threshold: float = 0.10
    audio_discussion_threshold: float = 0.02
    audio_chaotic_threshold: float = 0.08

    def classify(
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
