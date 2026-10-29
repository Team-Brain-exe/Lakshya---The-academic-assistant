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


# ---------------------------------------------------------------------------
# Live routes (Postgres)
# ---------------------------------------------------------------------------

from pydantic import BaseModel
from sqlalchemy import text

from ..db import get_conn
from ..deps import get_current_user, require_faculty
from ..errors import AppError
from ..pg.calendar import PostgresCalendarStore
from ..pg.common import as_uuid, enrolled_subject_ids, subject_for_faculty, subject_for_user
from ..services.calendar import (
    CalendarPermissionError,
    CalendarValidationError,
    create_event,
    delete_event,
    update_event,
)

router = APIRouter(tags=["calendar"])


class EventCreate(BaseModel):
    subject_id: str
    type: str
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    section: str | None = None
    quiz_id: str | None = None
    module_id: str | None = None


class EventPatch(BaseModel):
    type: str | None = None
    title: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    section: str | None = None
    quiz_id: str | None = None
    module_id: str | None = None


def _translate(exc: Exception) -> AppError:
    if isinstance(exc, CalendarPermissionError):
        return AppError(403, "FORBIDDEN", str(exc))
    if isinstance(exc, CalendarValidationError):
        return AppError(422, "VALIDATION_ERROR", str(exc))
    return AppError(404, "NOT_FOUND", "Event not found")


def _check_links(conn, subject_id: str, quiz_id: str | None, module_id: str | None) -> None:
    """A linked quiz or module must belong to the same subject."""
    if quiz_id and conn.execute(
        text("SELECT 1 FROM quizzes WHERE id = :q AND subject_id = :s"),
        {"q": as_uuid(quiz_id, "Quiz"), "s": subject_id},
    ).fetchone() is None:
        raise AppError(404, "NOT_FOUND", "Quiz not found")
    if module_id and conn.execute(
        text("SELECT 1 FROM modules WHERE id = :m AND subject_id = :s"),
        {"m": as_uuid(module_id, "Module"), "s": subject_id},
    ).fetchone() is None:
        raise AppError(404, "NOT_FOUND", "Module not found")


def _owned_event(conn, store: PostgresCalendarStore, event_id: str, user: dict):
    event = store.get_event(event_id)
    if event is None:
        raise AppError(404, "NOT_FOUND", "Event not found")
    subject_for_faculty(conn, event.subject_id, user)  # 404 if it is another faculty member's
    return event


@router.post("/events", status_code=201)
def post_event(body: EventCreate, conn=Depends(get_conn), user=Depends(require_faculty)):
    sid = str(subject_for_faculty(conn, body.subject_id, user)["id"])
    _check_links(conn, sid, body.quiz_id, body.module_id)
    try:
        event = create_event(
            PostgresCalendarStore(conn), user, sid, body.type, body.title.strip(), body.starts_at,
            ends_at=body.ends_at, section=body.section, quiz_id=body.quiz_id, module_id=body.module_id,
        )
    except (CalendarPermissionError, CalendarValidationError) as exc:
        raise _translate(exc) from None
    return event.to_dict()


@router.get("/events")
def get_events(
    subject_id: str | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    conn=Depends(get_conn),
    user=Depends(get_current_user),
):
    if user["role"] == "faculty":
        if subject_id:
            allowed = [str(subject_for_faculty(conn, subject_id, user)["id"])]
        else:
            rows = conn.execute(
                text("SELECT id FROM subjects WHERE faculty_user_id = :f"), {"f": user["user_id"]}
            ).fetchall()
            allowed = [str(r[0]) for r in rows]
        sections: dict[str, str] = {}
    else:
        if subject_id:
            allowed = [str(subject_for_user(conn, subject_id, user)["id"])]
        else:
            allowed = enrolled_subject_ids(conn, user["student_id"])
        rows = conn.execute(
            text("SELECT subject_id, section FROM enrollments WHERE student_id = :s"), {"s": user["student_id"]}
        ).fetchall()
        sections = {str(r[0]): r[1] for r in rows}

    events = PostgresCalendarStore(conn).list_events(allowed, from_, to)
    if user["role"] == "student":
        # Section-specific events are only for that section.
        events = [e for e in events if e.section is None or e.section == sections.get(e.subject_id)]
    return [e.to_dict() for e in events]


@router.patch("/events/{event_id}")
def patch_event(event_id: str, body: EventPatch, conn=Depends(get_conn), user=Depends(require_faculty)):
    store = PostgresCalendarStore(conn)
    _owned_event(conn, store, event_id, user)
    updates = body.model_dump(exclude_unset=True)
    if updates.get("title") is not None:
        updates["title"] = updates["title"].strip()
    existing = store.get_event(event_id)
    if "quiz_id" in updates or "module_id" in updates:
        _check_links(conn, existing.subject_id, updates.get("quiz_id"), updates.get("module_id"))
    try:
        return update_event(store, user, event_id, updates).to_dict()
    except (CalendarPermissionError, CalendarValidationError, KeyError) as exc:
        raise _translate(exc) from None


@router.delete("/events/{event_id}")
def remove_event(event_id: str, conn=Depends(get_conn), user=Depends(require_faculty)):
    store = PostgresCalendarStore(conn)
    _owned_event(conn, store, event_id, user)
    try:
        delete_event(store, user, event_id)
    except CalendarPermissionError as exc:
        raise _translate(exc) from None
    return {"deleted": True}
