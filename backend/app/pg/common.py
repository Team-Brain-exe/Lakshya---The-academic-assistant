"""Small helpers shared by the Postgres stores and the routers."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text

from ..errors import AppError


def as_uuid(value: Any, what: str = "Resource") -> str:
    """Return the canonical UUID string, or raise 404 for anything that is not one.

    A malformed id would otherwise reach Postgres and come back as a 500.
    """
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise AppError(404, "NOT_FOUND", f"{what} not found") from None


def to_str(value: Any) -> str | None:
    return None if value is None else str(value)


def to_float(value: Any) -> float | None:
    return None if value is None else float(value)


def subject_for_faculty(conn: Any, subject_id: str, user: dict) -> dict:
    """The subject row, if this faculty member owns it. Otherwise 404."""
    sid = as_uuid(subject_id, "Subject")
    row = conn.execute(
        text("SELECT * FROM subjects WHERE id = :id AND faculty_user_id = :fid"),
        {"id": sid, "fid": user["user_id"]},
    ).mappings().fetchone()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Subject not found")
    return dict(row)


def subject_for_student(conn: Any, subject_id: str, user: dict) -> dict:
    """The subject row, if this student is enrolled in it. Otherwise 404."""
    sid = as_uuid(subject_id, "Subject")
    if not user.get("student_id"):
        raise AppError(403, "FORBIDDEN", "Student access required")
    row = conn.execute(
        text(
            "SELECT s.* FROM subjects s "
            "JOIN enrollments e ON e.subject_id = s.id "
            "WHERE s.id = :id AND e.student_id = :stid"
        ),
        {"id": sid, "stid": user["student_id"]},
    ).mappings().fetchone()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Subject not found")
    return dict(row)


def subject_for_user(conn: Any, subject_id: str, user: dict) -> dict:
    """Faculty must own the subject, a student must be enrolled in it."""
    if user["role"] == "faculty":
        return subject_for_faculty(conn, subject_id, user)
    return subject_for_student(conn, subject_id, user)


def module_for_user(conn: Any, module_id: str, user: dict) -> dict:
    """The module row, if the user may see its subject. Otherwise 404."""
    mid = as_uuid(module_id, "Module")
    row = conn.execute(
        text("SELECT * FROM modules WHERE id = :id"), {"id": mid}
    ).mappings().fetchone()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Module not found")
    subject_for_user(conn, str(row["subject_id"]), user)
    return dict(row)


def enrolled_subject_ids(conn: Any, student_id: str) -> list[str]:
    rows = conn.execute(
        text("SELECT subject_id FROM enrollments WHERE student_id = :s"), {"s": student_id}
    ).fetchall()
    return [str(r[0]) for r in rows]
