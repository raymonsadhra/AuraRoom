"""
AuraRoom room snapshot model.

What this module does:
- Defines a typed room snapshot payload used across services and APIs.

How it contributes to AuraRoom:
- Gives a stable contract for live metrics, logging, and insights so modules
  can evolve independently.

Hardware interaction:
- Indirect. Fields represent values computed from camera and microphone input.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class RoomSnapshot:
    timestamp: str
    hour: int
    people_count: int
    motion_level: float
    audio_energy: float
    noise_level_label: str
    room_state: str
    insight_text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
