"""
AuraRoom audio pipeline.

What this module does:
- Captures continuous microphone audio, computes RMS energy, smooths it, and
  exposes a simple noise label (low/medium/high).

How it contributes to AuraRoom:
- Audio energy helps distinguish quiet focused work from active discussion and
  chaotic moments.

Hardware interaction:
- Direct. Reads from system microphone using sounddevice. If no mic is present,
  service degrades gracefully and returns low energy values.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import numpy as np

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - runtime dependency
    sd = None  # type: ignore


LOGGER = logging.getLogger(__name__)


class AudioService:
    def __init__(
        self,
        *,
        enabled: bool,
        samplerate: int,
        blocksize: int,
        device_index: int,
        smoothing_alpha: float,
        noise_low_threshold: float,
        noise_high_threshold: float,
    ) -> None:
        self.enabled = enabled
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.device_index = device_index
        self.smoothing_alpha = smoothing_alpha
        self.noise_low_threshold = noise_low_threshold
        self.noise_high_threshold = noise_high_threshold

        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._stream: Any = None

        self._audio_energy = 0.0
        self._noise_level_label = "low"
        self._last_audio_ts = 0.0

    def start(self) -> None:
        if not self.enabled:
            LOGGER.warning("Audio service disabled by config")
            return
        if sd is None:
            LOGGER.warning("sounddevice not available; audio service disabled")
            return
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="audio-service", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "audio_energy": round(self._audio_energy, 5),
                "noise_level_label": self._noise_level_label,
                "audio_last_frame_ts": self._last_audio_ts,
            }

    def _run_loop(self) -> None:
        try:
            # Mic assumption: default input device exists and accepts mono float32.
            self._stream = sd.InputStream(
                channels=1,
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                dtype="float32",
                device=None if self.device_index < 0 else self.device_index,
                callback=self._audio_callback,
            )
            self._stream.start()
            LOGGER.info("Audio stream started")
        except Exception as exc:
            LOGGER.error("Could not start microphone input stream: %s", exc)
            return

        while not self._stop_event.is_set():
            time.sleep(0.2)

        LOGGER.info("Audio service stopped")

    def _audio_callback(self, indata: np.ndarray, frames: int, _time: Any, status: Any) -> None:
        if status:
            LOGGER.debug("Audio callback status: %s", status)

        if frames <= 0 or indata.size == 0:
            return

        # RMS is a simple and robust proxy for loudness in a small-room demo.
        rms = float(np.sqrt(np.mean(np.square(indata))))

        with self._lock:
            prev = self._audio_energy
            smoothed = (self.smoothing_alpha * rms) + ((1.0 - self.smoothing_alpha) * prev)
            self._audio_energy = smoothed
            self._noise_level_label = self._label_noise(smoothed)
            self._last_audio_ts = time.time()

    def _label_noise(self, energy: float) -> str:
        if energy < self.noise_low_threshold:
            return "low"
        if energy < self.noise_high_threshold:
            return "medium"
        return "high"
