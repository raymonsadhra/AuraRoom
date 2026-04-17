"""
AuraRoom insight generation service.

What this module does:
- Builds short natural-language room insights from current metrics and recent
  history using either local templates or an optional LLM provider.

How it contributes to AuraRoom:
- Turns telemetry into clear story moments for demos, such as trend changes and
  behavior patterns over time.

Hardware interaction:
- Indirect. Consumes camera/mic-derived metrics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
import statistics
from typing import Any


class InsightProvider(ABC):
    @abstractmethod
    def generate(self, current: dict[str, Any], history: list[dict[str, Any]]) -> str:
        raise NotImplementedError


@dataclass(slots=True)
class LocalTemplateInsightProvider(InsightProvider):
    """Always-available deterministic insight provider.

    Local fallback is critical for live demos because it avoids cloud/API
    dependencies that can fail in unstable venue networks.
    """

    def generate(self, current: dict[str, Any], history: list[dict[str, Any]]) -> str:
        if not current:
            return "Waiting for room data."

        people = current.get("people_count", 0)
        state = current.get("room_state", "unknown")
        noise = current.get("noise_level_label", "low")

        parts: list[str] = [f"{people} people detected. Current state: {state}."]

        if noise == "low":
            parts.append("Room is acoustically calm.")
        elif noise == "medium":
            parts.append("Conversation-level audio is present.")
        else:
            parts.append("Noise is elevated right now.")

        trend = self._energy_trend(history)
        if trend:
            parts.append(trend)

        hourly = self._hourly_pattern(history)
        if hourly:
            parts.append(hourly)

        return " ".join(parts)

    def _energy_trend(self, history: list[dict[str, Any]]) -> str:
        if len(history) < 6:
            return ""
        recent = history[-3:]
        earlier = history[-6:-3]
        recent_avg = statistics.fmean(item.get("audio_energy", 0.0) for item in recent)
        earlier_avg = statistics.fmean(item.get("audio_energy", 0.0) for item in earlier)
        delta = recent_avg - earlier_avg

        if delta > 0.01:
            return "Energy has increased over the last few minutes."
        if delta < -0.01:
            return "Energy has decreased over the last few minutes."
        return "Energy level is relatively steady."

    def _hourly_pattern(self, history: list[dict[str, Any]]) -> str:
        if len(history) < 20:
            return ""

        buckets: dict[int, list[str]] = {}
        for item in history:
            hour = item.get("hour")
            state = item.get("room_state")
            if isinstance(hour, int) and isinstance(state, str):
                buckets.setdefault(hour, []).append(state)

        if not buckets:
            return ""

        best_hour = None
        best_focus_ratio = 0.0
        for hour, states in buckets.items():
            focused = sum(1 for s in states if s == "focused")
            ratio = focused / max(1, len(states))
            if ratio > best_focus_ratio:
                best_focus_ratio = ratio
                best_hour = hour

        if best_hour is None or best_focus_ratio < 0.5:
            return ""

        return f"Peak focus trend appears around {best_hour:02d}:00."


@dataclass(slots=True)
class OpenAIInsightProvider(InsightProvider):
    api_key: str
    model: str

    def generate(self, current: dict[str, Any], history: list[dict[str, Any]]) -> str:
        if not self.api_key:
            return "LLM mode configured, but OPENAI_API_KEY is missing."

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            short_history = history[-30:]
            prompt = (
                "You are an ambient room analyst. Return one short insight (1-2 sentences) "
                "about current room state and a useful trend. Be factual, concise, and avoid hype.\n"
                f"Current: {current}\n"
                f"Recent history: {short_history}\n"
            )
            resp = client.responses.create(
                model=self.model,
                input=prompt,
                max_output_tokens=90,
            )
            text = getattr(resp, "output_text", "").strip()
            return text or "LLM returned no text; using telemetry only."
        except Exception as exc:
            return f"LLM insight unavailable: {exc}."


@dataclass(slots=True)
class InsightService:
    mode: str
    provider: InsightProvider
    fallback_provider: InsightProvider

    @classmethod
    def build(
        cls,
        *,
        mode: str,
        llm_provider_name: str,
        openai_api_key: str,
        openai_model: str,
    ) -> "InsightService":
        fallback = LocalTemplateInsightProvider()
        mode_clean = mode.strip().lower()

        if mode_clean == "llm" and llm_provider_name == "openai":
            provider: InsightProvider = OpenAIInsightProvider(api_key=openai_api_key, model=openai_model)
        else:
            provider = fallback
            mode_clean = "local"

        return cls(mode=mode_clean, provider=provider, fallback_provider=fallback)

    def generate(self, current: dict[str, Any], history: list[dict[str, Any]]) -> str:
        text = self.provider.generate(current, history)

        # Keep the demo resilient: if LLM fails or returns warning text,
        # still provide a usable local insight.
        if self.mode == "llm" and ("unavailable" in text.lower() or "missing" in text.lower()):
            local_text = self.fallback_provider.generate(current, history)
            return f"{local_text} (LLM fallback reason: {text})"

        return text


def summarize_history_states(history: list[dict[str, Any]]) -> dict[str, int]:
    """Helper used by API or dashboard summary cards."""
    counts = Counter(item.get("room_state", "unknown") for item in history)
    return dict(counts)
