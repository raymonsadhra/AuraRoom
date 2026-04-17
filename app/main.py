"""
AuraRoom Flask application entrypoint.

What this module does:
- Builds the Flask app, initializes orchestrator/services, registers routes,
  and handles lifecycle cleanup.

How it contributes to AuraRoom:
- Boots the full MVP stack so judges can open a browser and watch live room
  intelligence update in real time.

Hardware interaction:
- Indirect. Starts orchestrator, which controls camera and microphone services.
"""

from __future__ import annotations

import atexit
import logging
from pathlib import Path

from flask import Flask, send_from_directory

from app.api.routes import create_api_blueprint
from app.config import load_config
from app.orchestrator import AuraOrchestrator
from app.services.logger_service import LoggerService
from app.state import AppState


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
LOGGER = logging.getLogger(__name__)


def create_app() -> Flask:
    # Flask is chosen for this MVP because it has minimal boilerplate and is
    # easy to debug quickly during a weekend hackathon.
    cfg = load_config()
    static_dir = (Path(__file__).resolve().parent.parent / "static").as_posix()
    app = Flask(__name__, static_folder=static_dir, static_url_path="/static")

    state = AppState(history_max_items=cfg.history_max_items)
    logger_service = LoggerService(
        backend=cfg.log_backend,
        jsonl_path=cfg.log_path_jsonl,
        sqlite_path=cfg.log_path_sqlite,
    )

    orchestrator = AuraOrchestrator(config=cfg, state=state, logger_service=logger_service)

    app.register_blueprint(create_api_blueprint(state=state, logger_service=logger_service))

    @app.get("/static/<path:filename>")
    def static_files(filename: str) -> object:
        static_folder = app.static_folder or "static"
        return send_from_directory(static_folder, filename)

    @app.get("/dashboard")
    def dashboard() -> object:
        static_folder = app.static_folder or "static"
        return send_from_directory(static_folder, "index.html")

    orchestrator.start()
    atexit.register(orchestrator.stop)

    app.config["AURAROOM_CONFIG"] = cfg
    app.config["AURAROOM_STATE"] = state
    app.config["AURAROOM_ORCHESTRATOR"] = orchestrator

    LOGGER.info("%s initialized on %s:%s", cfg.app_name, cfg.host, cfg.port)
    return app


def run() -> None:
    cfg = load_config()
    app = create_app()
    app.run(host=cfg.host, port=cfg.port, debug=cfg.debug, threaded=True)


if __name__ == "__main__":
    run()
