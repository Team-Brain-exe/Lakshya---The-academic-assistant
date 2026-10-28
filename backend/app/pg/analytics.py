"""AnalyticsStore on Postgres: roster, CO config and per-attempt CO scores.

Reads student_co_scores (written by Aparna's submit) and rebuilds one AttemptScore per
graded attempt. The attempt rule (best, latest or average) is applied in code by
co_analytics through ATTEMPT_RULE, the same setting Aparna's submit uses to set the
`counted` flag, so the sheet and the flag agree. Per-question results (needed only for
the drill-down) are rebuilt by re-grading the stored answers with engine.grading.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import text

from ..engine.co_math import AttemptScore, COConfig, StudentInfo
from ..engine.grading import COMarks, QuestionKey, grade_attempt
from .common import as_uuid, to_float


class PostgresAnalyticsStore:
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    # -- course outcomes -------------------------------------------------

    def get_subject_cos(self, subject_id: str) -> list[COConfig]:
        rows = self.conn.execute(
            text(
                "SELECT number, threshold_pct, target_attainment_pct "
                "FROM course_outcomes WHERE subject_id = :sid ORDER BY number"
            ),
            {"sid": as_uuid(subject_id, "Subject")},
        ).fetchall()
        return [COConfig(int(r[0]), float(r[1]), float(r[2])) for r in rows]

    def get_co_by_id(self, co_id: str) -> COConfig | None:
        row = self.conn.execute(
            text(
                "SELECT number, threshold_pct, target_attainment_pct "
                "FROM course_outcomes WHERE id = :id"
            ),
            {"id": as_uuid(co_id, "Course outcome")},
        ).fetchone()
        return COConfig(int(row[0]), float(row[1]), float(row[2])) if row else None

    def co_numbers_to_ids(self, subject_id: str) -> dict[int, str]:
        rows = self.conn.execute(
            text("SELECT number, id FROM course_outcomes WHERE subject_id = :sid"),
            {"sid": as_uuid(subject_id, "Subject")},
        ).fetchall()
        return {int(r[0]): str(r[1]) for r in rows}

    # -- people ----------------------------------------------------------

    def get_subject_roster(self, subject_id: str) -> list[StudentInfo]:
        rows = self.conn.execute(
            text(
                "SELECT s.usn, s.name, e.section FROM enrollments e "
                "JOIN students s ON s.id = e.student_id "
                "WHERE e.subject_id = :sid ORDER BY s.usn"
            ),
            {"sid": as_uuid(subject_id, "Subject")},
        ).fetchall()
        return [StudentInfo(usn=r[0], name=r[1], section=r[2]) for r in rows]

    def get_student_by_usn(self, usn: str) -> StudentInfo | None:
        row = self.conn.execute(
            text(
                "SELECT s.usn, s.name, "
                "(SELECT e.section FROM enrollments e WHERE e.student_id = s.id LIMIT 1) "
                "FROM students s WHERE s.usn = :usn"
            ),
            {"usn": usn.strip().upper()},
        ).fetchone()
        return StudentInfo(usn=row[0], name=row[1], section=row[2]) if row else None

    # -- scores ----------------------------------------------------------

    def get_subject_attempts(self, subject_id: str) -> list[AttemptScore]:
        sid = as_uuid(subject_id, "Subject")
        rows = self.conn.execute(
            text(
                "SELECT s.attempt_id, st.usn, a.quiz_id, a.attempt_number, a.answers, "
                "       COALESCE(s.module_id, z.module_id) AS module_id, "
                "       c.number AS co_number, s.marks_obtained, s.max_marks "
                "FROM student_co_scores s "
                "JOIN quiz_attempts a ON a.id = s.attempt_id "
                "JOIN quizzes z ON z.id = a.quiz_id "
                "JOIN students st ON st.id = s.student_id "
                "JOIN course_outcomes c ON c.id = s.co_id "
                "WHERE s.subject_id = :sid AND a.submitted_at IS NOT NULL "
                "ORDER BY st.usn, a.quiz_id, a.attempt_number, c.number"
            ),
            {"sid": sid},
        ).mappings().fetchall()
        if not rows:
            return []

        quiz_ids = sorted({str(r["quiz_id"]) for r in rows})
        keys_by_quiz = self._question_keys(quiz_ids)

        grouped: dict[str, dict[str, Any]] = {}
        per_co: dict[str, dict[int, COMarks]] = defaultdict(dict)
        for r in rows:
            aid = str(r["attempt_id"])
            grouped.setdefault(aid, r)
            co = int(r["co_number"])
            per_co[aid][co] = COMarks(co=co, obtained=float(r["marks_obtained"]), maximum=float(r["max_marks"]))

        out: list[AttemptScore] = []
        for aid, r in grouped.items():
            quiz_id = str(r["quiz_id"])
            answers = r["answers"] or {}
            questions: tuple = ()
            keys = keys_by_quiz.get(quiz_id)
            if keys:
                try:
                    questions = grade_attempt(keys, answers).questions
                except ValueError:
                    questions = ()
            out.append(
                AttemptScore(
                    usn=r["usn"],
                    quiz_id=quiz_id,
                    module_id=str(r["module_id"]) if r["module_id"] else "unknown",
                    attempt_number=int(r["attempt_number"]),
                    per_co=per_co[aid],
                    questions=questions,
                )
            )
        return out

    def _question_keys(self, quiz_ids: list[str]) -> dict[str, list[QuestionKey]]:
        if not quiz_ids:
            return {}
        rows = self.conn.execute(
            text(
                "SELECT qq.quiz_id, q.id, c.number, q.correct_option, q.marks "
                "FROM quiz_questions qq "
                "JOIN questions q ON q.id = qq.question_id "
                "JOIN course_outcomes c ON c.id = q.co_id "
                "WHERE qq.quiz_id = ANY(CAST(:ids AS uuid[])) "
                "ORDER BY qq.quiz_id, qq.position"
            ),
            {"ids": "{" + ",".join(quiz_ids) + "}"},
        ).fetchall()
        keys: dict[str, list[QuestionKey]] = defaultdict(list)
        for quiz_id, qid, co, correct, marks in rows:
            keys[str(quiz_id)].append(
                QuestionKey(id=str(qid), co=int(co), correct_option=int(correct), marks=float(marks))
            )
        return dict(keys)

    def get_student_progress(self, student_id: str, subject_id: str) -> dict[str, Any]:
        rows = self.conn.execute(
            text(
                "SELECT a.quiz_id, a.attempt_number, a.total_score, a.max_score, a.submitted_at "
                "FROM quiz_attempts a JOIN quizzes z ON z.id = a.quiz_id "
                "WHERE a.student_id = :stid AND z.subject_id = :sid AND a.submitted_at IS NOT NULL "
                "ORDER BY a.submitted_at"
            ),
            {"stid": as_uuid(student_id, "Student"), "sid": as_uuid(subject_id, "Subject")},
        ).fetchall()
        return {
            "co_scores": [],
            "attempts": [
                {
                    "quiz_id": str(r[0]),
                    "attempt_number": int(r[1]),
                    "total_score": to_float(r[2]),
                    "max_score": to_float(r[3]),
                    "submitted_at": r[4].isoformat() if r[4] else None,
                }
                for r in rows
            ],
        }
