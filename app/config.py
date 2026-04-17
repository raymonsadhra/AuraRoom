"""
AuraRoom configuration module.

What this module does:
- Centralizes runtime settings loaded from environment variables.
- Keeps hackathon defaults practical for Raspberry Pi and laptop demos.

How it contributes to AuraRoom:
- Makes it easy to tune camera/audio sensitivity, insight mode, and API settings
  without changing source code during a live demo.

Hardware interaction:
- Indirect. Values here control how camera and microphone services access
  hardware devices and how often heavy inference runs on constrained CPUs.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore

if load_dotenv is not None:
    load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(slots=True)
class AppConfig:
    app_name: str = "AuraRoom"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Sampling and timing.
    sample_interval_sec: float = 2.0
    insight_interval_sec: float = 15.0
    history_max_items: int = 1800

    # Camera / vision settings.
    camera_index: int = 0
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30
    camera_fourcc: str = "MJPG"
    camera_use_v4l2: bool = True
    vision_enabled: bool = True
    yolo_model_name: str = "yolov8n.pt"
    yolo_conf_threshold: float = 0.35
    yolo_infer_every_n_frames: int = 10

    # Audio settings.
    audio_enabled: bool = True
    audio_samplerate: int = 16000
    audio_blocksize: int = 1024
    audio_device_index: int = -1  # -1 means system default input device
    audio_smoothing_alpha: float = 0.2
    noise_low_threshold: float = 0.015
    noise_high_threshold: float = 0.08

    # Logging settings.
    log_backend: str = "jsonl"  # jsonl or sqlite
    log_path_jsonl: str = "data/room_events.jsonl"
    log_path_sqlite: str = "data/room_events.db"

    # Insight settings.
    use_ml_anomaly: bool = True
    insight_mode: str = "local"  # local or llm
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent


def load_config() -> AppConfig:
    """Load settings from env vars with safe defaults for hackathon use."""
    return AppConfig(
        app_name=os.getenv("APP_NAME", "AuraRoom"),
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=_get_int("APP_PORT", 8000),
        debug=_get_bool("APP_DEBUG", False),
        sample_interval_sec=_get_float("SAMPLE_INTERVAL_SEC", 2.0),
        insight_interval_sec=_get_float("INSIGHT_INTERVAL_SEC", 15.0),
        history_max_items=_get_int("HISTORY_MAX_ITEMS", 1800),
        camera_index=_get_int("CAMERA_INDEX", 0),
        camera_width=_get_int("CAMERA_WIDTH", 640),
        camera_height=_get_int("CAMERA_HEIGHT", 480),
        camera_fps=_get_int("CAMERA_FPS", 30),
        camera_fourcc=os.getenv("CAMERA_FOURCC", "MJPG"),
        camera_use_v4l2=_get_bool("CAMERA_USE_V4L2", True),
        vision_enabled=_get_bool("VISION_ENABLED", True),
        yolo_model_name=os.getenv("YOLO_MODEL_NAME", "yolov8n.pt"),
        yolo_conf_threshold=_get_float("YOLO_CONF_THRESHOLD", 0.35),
        yolo_infer_every_n_frames=_get_int("YOLO_INFER_EVERY_N_FRAMES", 10),
        audio_enabled=_get_bool("AUDIO_ENABLED", True),
        audio_samplerate=_get_int("AUDIO_SAMPLERATE", 16000),
        audio_blocksize=_get_int("AUDIO_BLOCKSIZE", 1024),
        audio_device_index=_get_int("AUDIO_DEVICE_INDEX", -1),
        audio_smoothing_alpha=_get_float("AUDIO_SMOOTHING_ALPHA", 0.2),
        noise_low_threshold=_get_float("NOISE_LOW_THRESHOLD", 0.015),
        noise_high_threshold=_get_float("NOISE_HIGH_THRESHOLD", 0.08),
        log_backend=os.getenv("LOG_BACKEND", "jsonl").strip().lower(),
        log_path_jsonl=os.getenv("LOG_PATH_JSONL", "data/room_events.jsonl"),
        log_path_sqlite=os.getenv("LOG_PATH_SQLITE", "data/room_events.db"),
        use_ml_anomaly=_get_bool("USE_ML_ANOMALY", True),
        insight_mode=os.getenv("INSIGHT_MODE", "local").strip().lower(),
        llm_provider=os.getenv("LLM_PROVIDER", "openai").strip().lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    )
