"""
AuraRoom API routes.

What this module does:
- Exposes HTTP endpoints for live metrics, history, insights, and health checks.
- Serves the dashboard static page.

How it contributes to AuraRoom:
- Connects backend intelligence to the visualization layer used in demos.

Hardware interaction:
- Indirect. Reads state that comes from hardware-facing services.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, send_from_directory

from app.services.logger_service import LoggerService
from app.state import AppState


def create_api_blueprint(*, state: AppState, logger_service: LoggerService) -> Blueprint:
    bp = Blueprint("api", __name__)

    @bp.get("/")
    def index() -> object:
        static_dir = current_app.static_folder or "static"
        return send_from_directory(static_dir, "index.html")

    @bp.get("/api/current")
    def get_current() -> object:
        payload = state.get_current()
        payload.setdefault("insight_text", state.get_latest_insight())
        return jsonify(payload)

    @bp.get("/api/history")
    def get_history() -> object:
        history = logger_service.get_recent(limit=300)
        hourly = logger_service.get_hourly_summary(limit=1000)
        return jsonify({"history": history, "hourly_summary": hourly})

    @bp.get("/api/insights")
    def get_insights() -> object:
        history = logger_service.get_recent(limit=200)
        latest = state.get_latest_insight()
        return jsonify({"latest": latest, "history_tail": history[-20:]})

    @bp.get("/api/health")
    def health() -> object:
        current = state.get_current()
        return jsonify(
            {
                "status": "ok",
                "current_available": bool(current),
                "latest_timestamp": current.get("timestamp"),
            }
        )

    return bp
