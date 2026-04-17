"""
AuraRoom data logging service.

What this module does:
- Persists timestamped room snapshots to JSONL or SQLite.
- Provides read helpers for recent history and hourly summaries.

How it contributes to AuraRoom:
- Enables trend analysis and time-of-day insights beyond live telemetry.

Hardware interaction:
- Indirect. Stores outputs derived from hardware sensors.
"""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import sqlite3
from threading import Lock
from typing import Any


class LoggerService:
    def __init__(self, *, backend: str, jsonl_path: str, sqlite_path: str) -> None:
        self.backend = backend.strip().lower()
        self.jsonl_path = Path(jsonl_path)
        self.sqlite_path = Path(sqlite_path)
        self._lock = Lock()
        self._conn: sqlite3.Connection | None = None

        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        if self.backend == "sqlite":
            self._init_sqlite()
        elif self.backend != "jsonl":
            # Default to jsonl for maximal portability in hackathons.
            self.backend = "jsonl"

    def _init_sqlite(self) -> None:
        self._conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS room_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                hour INTEGER NOT NULL,
                people_count INTEGER NOT NULL,
                motion_level REAL NOT NULL,
                audio_energy REAL NOT NULL,
                noise_level_label TEXT NOT NULL,
                room_state TEXT NOT NULL,
                insight_text TEXT
            )
            """
        )
        self._conn.commit()

    def log_snapshot(self, snapshot: dict[str, Any]) -> None:
        with self._lock:
            if self.backend == "sqlite":
                self._write_sqlite(snapshot)
            else:
                self._write_jsonl(snapshot)

    def _write_jsonl(self, snapshot: dict[str, Any]) -> None:
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=True) + "\n")

    def _write_sqlite(self, snapshot: dict[str, Any]) -> None:
        if self._conn is None:
            return
        self._conn.execute(
            """
            INSERT INTO room_events (
                timestamp, hour, people_count, motion_level,
                audio_energy, noise_level_label, room_state, insight_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.get("timestamp"),
                int(snapshot.get("hour", 0)),
                int(snapshot.get("people_count", 0)),
                float(snapshot.get("motion_level", 0.0)),
                float(snapshot.get("audio_energy", 0.0)),
                str(snapshot.get("noise_level_label", "low")),
                str(snapshot.get("room_state", "unknown")),
                str(snapshot.get("insight_text", "")),
            ),
        )
        self._conn.commit()

    def get_recent(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            if self.backend == "sqlite":
                return self._read_recent_sqlite(limit)
            return self._read_recent_jsonl(limit)

    def _read_recent_jsonl(self, limit: int) -> list[dict[str, Any]]:
        if not self.jsonl_path.exists():
            return []

        # JSONL is simple and robust for long-running append-heavy workloads.
        lines = self.jsonl_path.read_text(encoding="utf-8").strip().splitlines()
        if not lines:
            return []

        rows: list[dict[str, Any]] = []
        for line in lines[-limit:]:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    def _read_recent_sqlite(self, limit: int) -> list[dict[str, Any]]:
        if self._conn is None:
            return []

        cur = self._conn.execute(
            """
            SELECT timestamp, hour, people_count, motion_level, audio_energy,
                   noise_level_label, room_state, insight_text
            FROM room_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
        out = [
            {
                "timestamp": row[0],
                "hour": row[1],
                "people_count": row[2],
                "motion_level": row[3],
                "audio_energy": row[4],
                "noise_level_label": row[5],
                "room_state": row[6],
                "insight_text": row[7] or "",
            }
            for row in rows
        ]
        out.reverse()
        return out

    def get_hourly_summary(self, limit: int = 500) -> list[dict[str, Any]]:
        recent = self.get_recent(limit=limit)
        buckets: dict[int, dict[str, Any]] = defaultdict(
            lambda: {
                "samples": 0,
                "avg_people": 0.0,
                "avg_motion": 0.0,
                "avg_audio_energy": 0.0,
                "focused_count": 0,
                "discussion_count": 0,
                "chaotic_count": 0,
                "empty_count": 0,
            }
        )

        for row in recent:
            hour = int(row.get("hour", 0))
            b = buckets[hour]
            b["samples"] += 1
            b["avg_people"] += float(row.get("people_count", 0))
            b["avg_motion"] += float(row.get("motion_level", 0.0))
            b["avg_audio_energy"] += float(row.get("audio_energy", 0.0))
            state = str(row.get("room_state", "unknown"))
            key = f"{state}_count"
            if key in b:
                b[key] += 1

        summary: list[dict[str, Any]] = []
        for hour in sorted(buckets.keys()):
            b = buckets[hour]
            samples = max(1, b["samples"])
            summary.append(
                {
                    "hour": hour,
                    "samples": b["samples"],
                    "avg_people": round(b["avg_people"] / samples, 2),
                    "avg_motion": round(b["avg_motion"] / samples, 4),
                    "avg_audio_energy": round(b["avg_audio_energy"] / samples, 5),
                    "focused_count": b["focused_count"],
                    "discussion_count": b["discussion_count"],
                    "chaotic_count": b["chaotic_count"],
                    "empty_count": b["empty_count"],
                }
            )

        return summary

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
