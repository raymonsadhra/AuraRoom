"""
Quick microphone sanity check for AuraRoom hardware setup.

What this script does:
- Runs audio capture and prints live energy/noise labels.

How it contributes to AuraRoom:
- Validates microphone availability and threshold behavior before demo.

Hardware interaction:
- Direct microphone access via sounddevice.
"""

from __future__ import annotations

import time
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import load_config
from app.services.audio_service import AudioService


def main() -> None:
    cfg = load_config()
    service = AudioService(
        enabled=True,
        samplerate=cfg.audio_samplerate,
        blocksize=cfg.audio_blocksize,
        device_index=cfg.audio_device_index,
        smoothing_alpha=cfg.audio_smoothing_alpha,
        noise_low_threshold=cfg.noise_low_threshold,
        noise_high_threshold=cfg.noise_high_threshold,
    )
    service.start()

    print("Audio test running. Speak near mic; press Ctrl+C to stop.")
    try:
        while True:
            print(service.get_metrics())
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()


if __name__ == "__main__":
    main()
