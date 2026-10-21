"""Calendar service and agent tool functions.

Handles event scheduling, listing, moving, and deletion with strict role
and enrollment checks as required by arya.md task 11 and docs/api-contract.md section 10.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, Sequence

VALID_EVENT_TYPES = ("quiz", "assignment", "exam", "teaching", "custom")


class CalendarPermissionError(Exception):
    """Raised when an operation violates role or enrollment boundaries."""


class CalendarValidationError(Exception):
    """Raised when event attributes are invalid."""


@dataclass(frozen=True)
class CalendarEvent:
    id: str
    subject_id: str
    type: str  # 'quiz', 'assignment', 'exam', 'teaching', 'custom'
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    section: str | None = None
    quiz_id: str | None = None
    module_id: str | None = None
    created_by: str | None = None
    created_by_agent: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "type": self.type,
            "title": self.title,
            "starts_at": self.starts_at.isoformat(),
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "section": self.section,
            "quiz_id": self.quiz_id,
            "module_id": self.module_id,
            "created_by": self.created_by,
            "created_by_agent": self.created_by_agent,
            "created_at": self.created_at.isoformat(),
        }


class CalendarStore(Protocol):
    """Protocol for event storage."""

    def save_event(self, event: CalendarEvent) -> CalendarEvent: ...

    def get_event(self, event_id: str) -> CalendarEvent | None: ...

    def update_event(self, event_id: str, updates: dict[str, Any]) -> CalendarEvent | None: ...

    def delete_event(self, event_id: str) -> bool: ...

    def list_events(
        self,
        subject_ids: Sequence[str] | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> list[CalendarEvent]: ...


class InMemoryCalendarStore:
    """In-memory event store for unit tests and local execution."""

    def __init__(self) -> None:
        self._events: dict[str, CalendarEvent] = {}

    def save_event(self, event: CalendarEvent) -> CalendarEvent:
        self._events[event.id] = event
        return event

    def get_event(self, event_id: str) -> CalendarEvent | None:
        return self._events.get(event_id)

    def update_event(self, event_id: str, updates: dict[str, Any]) -> CalendarEvent | None:
        curr = self._events.get(event_id)
        if not curr:
            return None
        d = {
            "id": curr.id,
            "subject_id": updates.get("subject_id", curr.subject_id),
            "type": updates.get("type", curr.type),
            "title": updates.get("title", curr.title),
            "starts_at": updates.get("starts_at", curr.starts_at),
            "ends_at": updates.get("ends_at", curr.ends_at) if "ends_at" in updates else curr.ends_at,
            "section": updates.get("section", curr.section) if "section" in updates else curr.section,
            "quiz_id": updates.get("quiz_id", curr.quiz_id) if "quiz_id" in updates else curr.quiz_id,
            "module_id": updates.get("module_id", curr.module_id) if "module_id" in updates else curr.module_id,
            "created_by": curr.created_by,
            "created_by_agent": updates.get("created_by_agent", curr.created_by_agent),
            "created_at": curr.created_at,
        }
        updated = CalendarEvent(**d)
        self._events[event_id] = updated
        return updated

    def delete_event(self, event_id: str) -> bool:
        if event_id in self._events:
            del self._events[event_id]
            return True
        return False

    def list_events(
        self,
        subject_ids: Sequence[str] | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> list[CalendarEvent]:
        res = list(self._events.values())
        if subject_ids is not None:
            sub_set = set(subject_ids)
            res = [e for e in res if e.subject_id in sub_set]
        if from_time is not None:
            res = [e for e in res if e.starts_at >= from_time]
        if to_time is not None:
            res = [e for e in res if e.starts_at <= to_time]
        res.sort(key=lambda e: e.starts_at)
        return res


def _validate_event_args(
    event_type: str, starts_at: datetime, ends_at: datetime | None = None
) -> None:
    if event_type not in VALID_EVENT_TYPES:
        raise CalendarValidationError(
            f"Invalid event type {event_type!r}. Must be one of {VALID_EVENT_TYPES}"
        )
    if ends_at is not None and ends_at < starts_at:
        raise CalendarValidationError(
            f"Event ends_at ({ends_at}) cannot be earlier than starts_at ({starts_at})"
        )


def create_event(
    store: CalendarStore,
    current_user: dict[str, Any],
    subject_id: str,
    event_type: str,
    title: str,
    starts_at: datetime,
    *,
    ends_at: datetime | None = None,
    section: str | None = None,
    quiz_id: str | None = None,
    module_id: str | None = None,
    created_by_agent: bool = False,
    event_id: str | None = None,
) -> CalendarEvent:
    """Create an event. Faculty only (students receive 403 / CalendarPermissionError)."""
    role = current_user.get("role")
    if role != "faculty":
        raise CalendarPermissionError("Only faculty members can create calendar events.")

    _validate_event_args(event_type, starts_at, ends_at)

    event = CalendarEvent(
        id=event_id or str(uuid.uuid4()),
        subject_id=subject_id,
        type=event_type,
        title=title,
        starts_at=starts_at,
        ends_at=ends_at,
        section=section,
        quiz_id=quiz_id,
        module_id=module_id,
        created_by=current_user.get("user_id"),
        created_by_agent=created_by_agent,
    )
    return store.save_event(event)


def list_events(
    store: CalendarStore,
    current_user: dict[str, Any],
    *,
    subject_id: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    student_enrolled_subjects: Sequence[str] | None = None,
) -> list[CalendarEvent]:
    """List events with role and enrollment scoping.
    
    Students are strictly restricted to events for subjects they are enrolled in.
    """
    role = current_user.get("role")
    allowed_subjects: list[str] | None = None

    if role == "student":
        enrolled = list(student_enrolled_subjects or [])
        if subject_id is not None:
            if subject_id not in enrolled:
                raise CalendarPermissionError("Students can only view events for enrolled subjects.")
            allowed_subjects = [subject_id]
        else:
            allowed_subjects = enrolled
    elif subject_id is not None:
        allowed_subjects = [subject_id]

    return store.list_events(
        subject_ids=allowed_subjects, from_time=from_time, to_time=to_time
    )


def update_event(
    store: CalendarStore,
    current_user: dict[str, Any],
    event_id: str,
    updates: dict[str, Any],
) -> CalendarEvent:
    """Update or move an event. Faculty only."""
    role = current_user.get("role")
    if role != "faculty":
        raise CalendarPermissionError("Only faculty members can update calendar events.")

    existing = store.get_event(event_id)
    if not existing:
        raise KeyError(f"Event {event_id} not found.")

    new_type = updates.get("type", existing.type)
    new_starts = updates.get("starts_at", existing.starts_at)
    new_ends = updates.get("ends_at", existing.ends_at) if "ends_at" in updates else existing.ends_at
    _validate_event_args(new_type, new_starts, new_ends)

    updated = store.update_event(event_id, updates)
    if not updated:
        raise KeyError(f"Event {event_id} not found.")
    return updated


def delete_event(
    store: CalendarStore,
    current_user: dict[str, Any],
    event_id: str,
) -> bool:
    """Delete an event. Faculty only."""
    role = current_user.get("role")
    if role != "faculty":
        raise CalendarPermissionError("Only faculty members can delete calendar events.")

    return store.delete_event(event_id)


def auto_create_quiz_event(
    store: CalendarStore,
    current_user: dict[str, Any],
    subject_id: str,
    quiz_id: str,
    title: str,
    opens_at: datetime,
    closes_at: datetime | None = None,
) -> CalendarEvent:
    """Automatically create an event when a quiz is published."""
    return create_event(
        store=store,
        current_user=current_user,
        subject_id=subject_id,
        event_type="quiz",
        title=f"Quiz: {title}",
        starts_at=opens_at,
        ends_at=closes_at,
        quiz_id=quiz_id,
    )


# --- Agent tool functions ---

def schedule_event_tool(
    store: CalendarStore,
    session_user: dict[str, Any],
    subject_id: str,
    type: str,
    title: str,
    starts_at: str,
    ends_at: str | None = None,
    section: str | None = None,
    quiz_id: str | None = None,
    module_id: str | None = None,
) -> dict[str, Any]:
    """Agent tool to propose or create a scheduled event."""
    st = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
    et = datetime.fromisoformat(ends_at.replace("Z", "+00:00")) if ends_at else None

    event = create_event(
        store=store,
        current_user=session_user,
        subject_id=subject_id,
        event_type=type,
        title=title,
        starts_at=st,
        ends_at=et,
        section=section,
        quiz_id=quiz_id,
        module_id=module_id,
        created_by_agent=True,
    )
    return {"status": "created", "event": event.to_dict()}


def list_events_tool(
    store: CalendarStore,
    session_user: dict[str, Any],
    subject_id: str | None = None,
    from_time: str | None = None,
    to_time: str | None = None,
    student_enrolled_subjects: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Agent tool to list events scoped to the session user."""
    ft = datetime.fromisoformat(from_time.replace("Z", "+00:00")) if from_time else None
    tt = datetime.fromisoformat(to_time.replace("Z", "+00:00")) if to_time else None

    events = list_events(
        store=store,
        current_user=session_user,
        subject_id=subject_id,
        from_time=ft,
        to_time=tt,
        student_enrolled_subjects=student_enrolled_subjects,
    )
    return [e.to_dict() for e in events]

