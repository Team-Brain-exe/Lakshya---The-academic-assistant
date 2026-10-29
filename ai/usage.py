"""Adapters from AI callbacks to the existing backend usage service."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

try:
    from app.services.usage import UsageStore, log_ai_call, log_tool_call
except ImportError:  # running package tools from the repository root
    from backend.app.services.usage import UsageStore, log_ai_call, log_tool_call


STEP_NAMES = {
    "co_tagging": "tagging",
    "quiz_generation": "generation",
    "agent": "agent",
    "qa": "qa",
    "study_plan": "study_plan",
    "flashcards": "flashcards",
}


def _token_count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def make_ai_usage_recorder(
    store: UsageStore,
    *,
    user_id: str | None = None,
    role: str | None = None,
) -> Callable[[dict[str, Any]], None]:
    """Create a callback suitable for the client, tagger, generator, and loop.

    Raw prompts, slide text, tool arguments and credentials are deliberately not
    copied into ``agent_logs``; only call metadata and token counts are stored.
    """
    def record(entry: dict[str, Any]) -> None:
        if not isinstance(entry, Mapping):
            return
        step = str(entry.get("step", "other"))
        args = {
            key: entry[key]
            for key in ("batch_number", "attempt")
            if key in entry and isinstance(entry[key], int) and not isinstance(entry[key], bool)
        }
        log_ai_call(
            store,
            step=STEP_NAMES.get(step, step),
            model=str(entry.get("model") or "unknown"),
            prompt_tokens=_token_count(entry.get("prompt_tokens")),
            completion_tokens=_token_count(entry.get("completion_tokens")),
            user_id=user_id or entry.get("user_id"),
            role=role or entry.get("role"),
            latency_ms=_token_count(entry.get("latency_ms")) if entry.get("latency_ms") is not None else None,
            args=args or None,
            result_summary=None,
            error=str(entry["error"]) if entry.get("error") else None,
        )
    return record


def make_tool_usage_recorder(
    store: UsageStore,
    *,
    user_id: str | None = None,
    role: str | None = None,
) -> Callable[[dict[str, Any]], None]:
    """Create a tool-call callback without persisting potentially sensitive args."""
    def record(entry: dict[str, Any]) -> None:
        if not isinstance(entry, Mapping):
            return
        name = entry.get("tool_name")
        if not isinstance(name, str) or not name:
            name = "unknown"
        log_tool_call(
            store,
            tool_name=name,
            user_id=user_id or entry.get("user_id"),
            role=role or entry.get("role"),
            latency_ms=_token_count(entry.get("latency_ms")) if entry.get("latency_ms") is not None else None,
            result_summary=str(entry.get("status")) if entry.get("status") else None,
            error=str(entry["error"]) if entry.get("error") else None,
        )
    return record
