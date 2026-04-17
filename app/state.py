"""
AuraRoom shared in-memory state.

What this module does:
- Stores the latest room snapshot, rolling history, and latest insights.
- Provides thread-safe getters/setters for concurrent background loops.

How it contributes to AuraRoom:
- Creates a single source of truth that feeds live API responses and dashboard
  updates without tight coupling between services.

Hardware interaction:
- Indirect. Hardware services publish sensor-derived values into this state.
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Deque


@dataclass
class AppState:
    history_max_items: int
    _lock: Lock = field(default_factory=Lock, init=False)
    _current: dict[str, Any] = field(default_factory=dict, init=False)
    _history: Deque[dict[str, Any]] = field(default_factory=deque, init=False)
    _latest_insight: str = field(default="", init=False)

    def update_current(self, snapshot: dict[str, Any]) -> None:
        with self._lock:
            self._current = deepcopy(snapshot)

    def add_snapshot(self, snapshot: dict[str, Any]) -> None:
        with self._lock:
            self._history.append(deepcopy(snapshot))
            if len(self._history) > self.history_max_items:
                self._history.popleft()

    def set_latest_insight(self, text: str) -> None:
        with self._lock:
            self._latest_insight = text

    def get_latest_insight(self) -> str:
        with self._lock:
            return self._latest_insight

    def get_current(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._current)

    def get_history(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._history)
        return items[-limit:]
