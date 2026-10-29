"""CalendarStore on Postgres (events table)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import text

from ..services.calendar import CalendarEvent
from .common import as_uuid, to_str

_COLS = (
    "id, subject_id, section, type, title, starts_at, ends_at, quiz_id, module_id, "
    "created_by, created_by_agent, created_at"
)
_UPDATABLE = {"section", "type", "title", "starts_at", "ends_at", "quiz_id", "module_id"}


def _row_to_event(r: Any) -> CalendarEvent:
    return CalendarEvent(
        id=str(r["id"]),
        subject_id=str(r["subject_id"]),
        type=r["type"],
        title=r["title"],
        starts_at=r["starts_at"],
        ends_at=r["ends_at"],
        section=r["section"],
        quiz_id=to_str(r["quiz_id"]),
        module_id=to_str(r["module_id"]),
        created_by=to_str(r["created_by"]),
        created_by_agent=bool(r["created_by_agent"]),
        created_at=r["created_at"],
    )


class PostgresCalendarStore:
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def save_event(self, event: CalendarEvent) -> CalendarEvent:
        row = self.conn.execute(
            text(
                "INSERT INTO events (subject_id, section, type, title, starts_at, ends_at, "
                "quiz_id, module_id, created_by, created_by_agent) "
                "VALUES (:sub, :sec, :type, :title, :start, :end, :quiz, :mod, :by, :agent) "
                f"RETURNING {_COLS}"
            ),
            {
                "sub": as_uuid(event.subject_id, "Subject"),
                "sec": event.section,
                "type": event.type,
                "title": event.title,
                "start": event.starts_at,
                "end": event.ends_at,
                "quiz": as_uuid(event.quiz_id, "Quiz") if event.quiz_id else None,
                "mod": as_uuid(event.module_id, "Module") if event.module_id else None,
                "by": event.created_by,
                "agent": event.created_by_agent,
            },
        ).mappings().fetchone()
        return _row_to_event(row)

    def get_event(self, event_id: str) -> CalendarEvent | None:
        row = self.conn.execute(
            text(f"SELECT {_COLS} FROM events WHERE id = :id"), {"id": as_uuid(event_id, "Event")}
        ).mappings().fetchone()
        return _row_to_event(row) if row else None

    def update_event(self, event_id: str, updates: dict[str, Any]) -> CalendarEvent | None:
        fields = {k: v for k, v in updates.items() if k in _UPDATABLE}
        if not fields:
            return self.get_event(event_id)
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        params = dict(fields)
        params["id"] = as_uuid(event_id, "Event")
        row = self.conn.execute(
            text(f"UPDATE events SET {sets} WHERE id = :id RETURNING {_COLS}"), params
        ).mappings().fetchone()
        return _row_to_event(row) if row else None

    def delete_event(self, event_id: str) -> bool:
        result = self.conn.execute(
            text("DELETE FROM events WHERE id = :id"), {"id": as_uuid(event_id, "Event")}
        )
        return result.rowcount > 0

    def list_events(
        self,
        subject_ids: Sequence[str] | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> list[CalendarEvent]:
        where, params = [], {}
        if subject_ids is not None:
            if not subject_ids:
                return []
            where.append("subject_id = ANY(CAST(:subs AS uuid[]))")
            params["subs"] = "{" + ",".join(as_uuid(s, "Subject") for s in subject_ids) + "}"
        if from_time is not None:
            where.append("starts_at >= :from_t")
            params["from_t"] = from_time
        if to_time is not None:
            where.append("starts_at <= :to_t")
            params["to_t"] = to_time
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        rows = self.conn.execute(
            text(f"SELECT {_COLS} FROM events{clause} ORDER BY starts_at"), params
        ).mappings().fetchall()
        return [_row_to_event(r) for r in rows]
