"""Confirmation executors for proposed calendar actions.

A proposal saves nothing. The executor runs only after the faculty user approves it, using
the arguments stored with the proposal and the user from the session. Times must carry a
timezone offset, so a stored event always means one exact moment.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..errors import AppError

EventType = Literal["quiz", "assignment", "exam", "teaching", "custom"]


class ScheduleEventArgs(BaseModel):
    """Mirrors the propose_schedule_event entry in ai/schemas/agent-tools.json."""

    model_config = ConfigDict(extra="forbid")

    subject_id: str = Field(min_length=1)
    type: EventType
    title: str = Field(min_length=1, max_length=200)
    starts_at: str
    ends_at: str | None = None
    section: str | None = None
    quiz_id: str | None = None
    module_id: str | None = None


def parse_aware_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppError(422, "INVALID_TIME", f"{field} must be an ISO 8601 date and time.") from exc
    if parsed.tzinfo is None:
        raise AppError(422, "INVALID_TIME", f"{field} needs a timezone offset, for example +05:30.")
    return parsed


def make_schedule_executor(
    store: Any,
    create_event: Callable[..., Any],
) -> Callable[[dict[str, Any], dict[str, Any]], Any]:
    """Return the confirmation executor for propose_schedule_event."""

    def execute(args: dict[str, Any], current_user: dict[str, Any]) -> Any:
        if current_user.get("role") != "faculty":
            raise AppError(403, "FORBIDDEN", "Only faculty can schedule calendar events.")
        data = ScheduleEventArgs.model_validate(args)
        starts_at = parse_aware_datetime(data.starts_at, "starts_at")
        ends_at = parse_aware_datetime(data.ends_at, "ends_at") if data.ends_at else None
        event = create_event(
            store,
            current_user,
            data.subject_id,
            data.type,
            data.title,
            starts_at,
            ends_at=ends_at,
            section=data.section,
            quiz_id=data.quiz_id,
            module_id=data.module_id,
            created_by_agent=True,
        )
        return event.to_dict()

    return execute
