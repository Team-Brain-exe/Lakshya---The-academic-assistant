"""Study plan, flashcard and note stores on Postgres."""

from __future__ import annotations

import json
from typing import Any, Sequence

from sqlalchemy import text

from ..services.study_material import Flashcard, Note
from ..services.study_plan import StudentStudyPlan
from .common import as_uuid, to_str


def _jsonb(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


class PostgresStudyPlanStore:
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def save_plan(self, plan: StudentStudyPlan) -> None:
        weak = [as_uuid(w) for w in plan.weak_co_ids]
        self.conn.execute(
            text(
                "INSERT INTO study_plans (id, student_id, subject_id, weak_co_ids, plan, generated_at) "
                "VALUES (:id, :stid, :sid, CAST(:weak AS uuid[]), CAST(:plan AS jsonb), :at)"
            ),
            {
                "id": as_uuid(plan.id),
                "stid": as_uuid(plan.student_id, "Student"),
                "sid": as_uuid(plan.subject_id, "Subject"),
                "weak": "{" + ",".join(weak) + "}",
                "plan": json.dumps(plan.plan),
                "at": plan.generated_at,
            },
        )

    def get_latest_plan(self, student_id: str, subject_id: str) -> StudentStudyPlan | None:
        row = self.conn.execute(
            text(
                "SELECT id, student_id, subject_id, weak_co_ids, plan, generated_at "
                "FROM study_plans WHERE student_id = :stid AND subject_id = :sid "
                "ORDER BY generated_at DESC LIMIT 1"
            ),
            {"stid": as_uuid(student_id, "Student"), "sid": as_uuid(subject_id, "Subject")},
        ).mappings().fetchone()
        if row is None:
            return None
        return StudentStudyPlan(
            id=str(row["id"]),
            student_id=str(row["student_id"]),
            subject_id=str(row["subject_id"]),
            weak_co_ids=[str(w) for w in (row["weak_co_ids"] or [])],
            plan=_jsonb(row["plan"]),
            generated_at=row["generated_at"],
        )


class PostgresStudyMaterialStore:
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def save_flashcards(self, cards: Sequence[Flashcard]) -> None:
        for c in cards:
            self.conn.execute(
                text(
                    "INSERT INTO flashcards (id, module_id, co_id, front, back) "
                    "VALUES (:id, :m, :co, :f, :b)"
                ),
                {
                    "id": as_uuid(c.id),
                    "m": as_uuid(c.module_id, "Module"),
                    "co": as_uuid(c.co_id) if c.co_id else None,
                    "f": c.front,
                    "b": c.back,
                },
            )

    def save_notes(self, notes: Sequence[Note]) -> None:
        for n in notes:
            self.conn.execute(
                text(
                    "INSERT INTO notes (id, module_id, co_id, title, body) "
                    "VALUES (:id, :m, :co, :t, :b)"
                ),
                {
                    "id": as_uuid(n.id),
                    "m": as_uuid(n.module_id, "Module"),
                    "co": as_uuid(n.co_id) if n.co_id else None,
                    "t": n.title,
                    "b": n.body,
                },
            )

    def list_flashcards(self, module_id: str) -> list[Flashcard]:
        rows = self.conn.execute(
            text(
                "SELECT id, module_id, co_id, front, back, created_at FROM flashcards "
                "WHERE module_id = :m ORDER BY created_at, id"
            ),
            {"m": as_uuid(module_id, "Module")},
        ).mappings().fetchall()
        return [
            Flashcard(str(r["id"]), str(r["module_id"]), to_str(r["co_id"]), r["front"], r["back"], r["created_at"])
            for r in rows
        ]

    def list_notes(self, module_id: str) -> list[Note]:
        rows = self.conn.execute(
            text(
                "SELECT id, module_id, co_id, title, body, created_at FROM notes "
                "WHERE module_id = :m ORDER BY created_at, id"
            ),
            {"m": as_uuid(module_id, "Module")},
        ).mappings().fetchall()
        return [
            Note(str(r["id"]), str(r["module_id"]), to_str(r["co_id"]), r["title"], r["body"], r["created_at"])
            for r in rows
        ]

    def has_material_for_module(self, module_id: str) -> bool:
        mid = as_uuid(module_id, "Module")
        return bool(
            self.conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM flashcards WHERE module_id = :m) "
                    "OR EXISTS (SELECT 1 FROM notes WHERE module_id = :m)"
                ),
                {"m": mid},
            ).scalar()
        )

    def delete_for_module(self, module_id: str) -> None:
        mid = as_uuid(module_id, "Module")
        self.conn.execute(text("DELETE FROM flashcards WHERE module_id = :m"), {"m": mid})
        self.conn.execute(text("DELETE FROM notes WHERE module_id = :m"), {"m": mid})


def subject_flashcards_with_co(conn: Any, subject_id: str) -> list[dict[str, Any]]:
    """All flashcards of a subject, each with its CO number (for study-plan linking)."""
    rows = conn.execute(
        text(
            "SELECT f.id, co.number, f.front, f.back FROM flashcards f "
            "JOIN modules m ON m.id = f.module_id "
            "JOIN course_outcomes co ON co.id = f.co_id "
            "WHERE m.subject_id = :s ORDER BY co.number, f.created_at"
        ),
        {"s": as_uuid(subject_id, "Subject")},
    ).fetchall()
    return [{"id": str(r[0]), "co_number": int(r[1]), "front": r[2], "back": r[3]} for r in rows]
