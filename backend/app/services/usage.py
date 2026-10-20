"""Usage logging and token-cost aggregation service.

Logs every AI call and tool call into agent_logs, and calculates
usage totals per step for Danwin's cost tracking page.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Protocol, Sequence


@dataclass(frozen=True)
class UsageEntry:
    id: str
    kind: str  # 'ai_call' or 'tool_call'
    step: str  # 'tagging', 'generation', 'agent', 'qa', 'study_plan', 'flashcards', etc.
    user_id: str | None = None
    role: str | None = None
    model: str | None = None
    tool_name: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int | None = None
    args: dict[str, Any] | None = None
    result_summary: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class StepUsageSummary:
    step: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


class UsageStore(Protocol):
    """Protocol for logging and retrieving agent and AI usage."""

    def record(self, entry: UsageEntry) -> None: ...

    def list_entries(
        self, from_time: datetime | None = None, to_time: datetime | None = None
    ) -> Sequence[UsageEntry]: ...


class InMemoryUsageStore:
    """In-memory store for unit testing and local fallback."""

    def __init__(self) -> None:
        self.entries: list[UsageEntry] = []

    def record(self, entry: UsageEntry) -> None:
        self.entries.append(entry)

    def list_entries(
        self, from_time: datetime | None = None, to_time: datetime | None = None
    ) -> list[UsageEntry]:
        filtered = self.entries
        if from_time is not None:
            filtered = [e for e in filtered if e.created_at >= from_time]
        if to_time is not None:
            filtered = [e for e in filtered if e.created_at <= to_time]
        return list(filtered)


def log_ai_call(
    store: UsageStore,
    step: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    *,
    user_id: str | None = None,
    role: str | None = None,
    latency_ms: int | None = None,
    args: dict[str, Any] | None = None,
    result_summary: str | None = None,
    error: str | None = None,
    entry_id: str | None = None,
    created_at: datetime | None = None,
) -> UsageEntry:
    """Log one AI invocation with token counts."""
    p_tokens = max(0, prompt_tokens)
    c_tokens = max(0, completion_tokens)
    tot_tokens = p_tokens + c_tokens

    entry = UsageEntry(
        id=entry_id or str(uuid.uuid4()),
        kind="ai_call",
        step=step,
        user_id=user_id,
        role=role,
        model=model,
        tool_name=None,
        prompt_tokens=p_tokens,
        completion_tokens=c_tokens,
        total_tokens=tot_tokens,
        latency_ms=latency_ms,
        args=args,
        result_summary=result_summary,
        error=error,
        created_at=created_at or datetime.now(timezone.utc),
    )
    store.record(entry)
    return entry


def log_tool_call(
    store: UsageStore,
    tool_name: str,
    *,
    step: str = "agent",
    user_id: str | None = None,
    role: str | None = None,
    latency_ms: int | None = None,
    args: dict[str, Any] | None = None,
    result_summary: str | None = None,
    error: str | None = None,
    entry_id: str | None = None,
    created_at: datetime | None = None,
) -> UsageEntry:
    """Log one tool invocation."""
    entry = UsageEntry(
        id=entry_id or str(uuid.uuid4()),
        kind="tool_call",
        step=step,
        user_id=user_id,
        role=role,
        model=None,
        tool_name=tool_name,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        latency_ms=latency_ms,
        args=args,
        result_summary=result_summary,
        error=error,
        created_at=created_at or datetime.now(timezone.utc),
    )
    store.record(entry)
    return entry


def aggregate_usage_by_step(
    entries: Iterable[UsageEntry],
) -> list[StepUsageSummary]:
    """Aggregate token usage and call counts per step.
    
    Returns a sorted list of summaries (highest total_tokens first, then alphabetically).
    """
    totals: dict[str, dict[str, int]] = {}

    for e in entries:
        st = e.step or "other"
        stats = totals.setdefault(st, {"calls": 0, "prompt": 0, "completion": 0, "total": 0})
        stats["calls"] += 1
        stats["prompt"] += e.prompt_tokens
        stats["completion"] += e.completion_tokens
        stats["total"] += e.total_tokens

    summaries = [
        StepUsageSummary(
            step=step,
            calls=v["calls"],
            prompt_tokens=v["prompt"],
            completion_tokens=v["completion"],
            total_tokens=v["total"],
        )
        for step, v in totals.items()
    ]
    summaries.sort(key=lambda s: (-s.total_tokens, s.step))
    return summaries


def get_usage_summary(
    store: UsageStore,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> list[dict[str, Any]]:
    """Retrieve usage summary per step for GET /usage/summary."""
    entries = store.list_entries(from_time=from_time, to_time=to_time)
    summaries = aggregate_usage_by_step(entries)
    return [s.to_dict() for s in summaries]

