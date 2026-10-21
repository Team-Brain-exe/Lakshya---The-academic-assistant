"""Calendar endpoints.

Section 10 of docs/api-contract.md:
- POST /events
- GET /events?subject_id=&from=&to=
- PATCH /events/{id}
- DELETE /events/{id}
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from app.services.calendar import (
    CalendarEvent,
    CalendarPermissionError,
    CalendarStore,
    CalendarValidationError,
    create_event,
    delete_event,
    list_events,
    update_event,
)

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, status
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


def format_error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


class CalendarRouterHandler:
    def __init__(self, store: CalendarStore, enrollment_provider: Any = None) -> None:
        self.store = store
        self.enrollment_provider = enrollment_provider

    def create(
        self,
        current_user: dict[str, Any],
        subject_id: str,
        type: str,
        title: str,
        starts_at: datetime,
        ends_at: datetime | None = None,
        section: str | None = None,
        quiz_id: str | None = None,
        module_id: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        try:
            ev = create_event(
                self.store,
                current_user=current_user,
                subject_id=subject_id,
                event_type=type,
                title=title,
                starts_at=starts_at,
                ends_at=ends_at,
                section=section,
                quiz_id=quiz_id,
                module_id=module_id,
            )
            return 201, ev.to_dict()
        except CalendarPermissionError as exc:
            return 403, format_error("FORBIDDEN", str(exc))
        except CalendarValidationError as exc:
            return 422, format_error("VALIDATION_ERROR", str(exc))

    def list(
        self,
        current_user: dict[str, Any],
        subject_id: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        student_id = current_user.get("student_id")
        enrolled = None
        if current_user.get("role") == "student" and self.enrollment_provider and student_id:
            enrolled = self.enrollment_provider(student_id)

        try:
            events = list_events(
                self.store,
                current_user=current_user,
                subject_id=subject_id,
                from_time=from_time,
                to_time=to_time,
                student_enrolled_subjects=enrolled,
            )
            return 200, [e.to_dict() for e in events]
        except CalendarPermissionError as exc:
            return 403, [format_error("FORBIDDEN", str(exc))]

    def update(
        self,
        current_user: dict[str, Any],
        event_id: str,
        updates: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        try:
            ev = update_event(self.store, current_user, event_id, updates)
            return 200, ev.to_dict()
        except CalendarPermissionError as exc:
            return 403, format_error("FORBIDDEN", str(exc))
        except CalendarValidationError as exc:
            return 422, format_error("VALIDATION_ERROR", str(exc))
        except KeyError:
            return 404, format_error("NOT_FOUND", f"Event {event_id} not found.")

    def delete(
        self,
        current_user: dict[str, Any],
        event_id: str,
    ) -> tuple[int, dict[str, Any]]:
        try:
            ok = delete_event(self.store, current_user, event_id)
            if not ok:
                return 404, format_error("NOT_FOUND", f"Event {event_id} not found.")
            return 200, {"deleted": True}
        except CalendarPermissionError as exc:
            return 403, format_error("FORBIDDEN", str(exc))


router = APIRouter() if HAS_FASTAPI else None

