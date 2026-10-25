"""PostgreSQL implementation of the QuizStore protocol.

Maps QuizRecord, QuestionRecord, QuizAttemptRecord, and StudentCOScoreRecord
to the database tables defined in backend/migrations/001_init.sql.
Uses SQLAlchemy Core text() queries — no ORM models.
"""
from __future__ import annotations

import json
import uuid as _uuid
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.services.quizzes import (
    AttemptLimitReachedError,
    QuestionRecord,
    QuizAttemptRecord,
    QuizRecord,
    QuizStore,
    StudentCOScoreRecord,
)


def _to_str(v: Any) -> str | None:
    """Convert a database value (UUID, etc.) to a string."""
    if v is None:
        return None
    if isinstance(v, _uuid.UUID):
        return str(v)
    return str(v)


def _json_loads(v: Any) -> Any:
    """Parse a JSONB value that may already be a dict/list or a string."""
    if v is None:
        return None
    if isinstance(v, str):
        return json.loads(v)
    return v


class PostgresQuizStore:
    """QuizStore backed by PostgreSQL via a SQLAlchemy Connection."""

    def __init__(self, conn: Any) -> None:
        self.conn = conn

    # -----------------------------------------------------------------
    # Internal row-mapping helpers
    # -----------------------------------------------------------------

    def _question_ids_for_quiz(self, quiz_id: str) -> tuple[str, ...]:
        rows = self.conn.execute(
            text(
                "SELECT question_id FROM quiz_questions "
                "WHERE quiz_id = :qid ORDER BY position"
            ),
            {"qid": str(quiz_id)},
        ).mappings().fetchall()
        return tuple(_to_str(r["question_id"]) for r in rows)

    def _row_to_quiz(self, row: Any) -> QuizRecord:
        question_ids = self._question_ids_for_quiz(row["id"])
        return QuizRecord(
            id=_to_str(row["id"]),
            module_id=_to_str(row["module_id"]),
            subject_id=_to_str(row["subject_id"]),
            title=row["title"],
            question_ids=question_ids,
            opens_at=row["opens_at"],
            closes_at=row["closes_at"],
            published=bool(row["published"]),
            published_at=row["published_at"],
            created_by=_to_str(row["created_by"]),
            created_at=row["created_at"] or datetime.now(),
        )

    def _row_to_question(self, row: Any) -> QuestionRecord:
        opts = _json_loads(row["options"])
        return QuestionRecord(
            id=_to_str(row["id"]),
            module_id=_to_str(row["module_id"]),
            co_id=_to_str(row["co_id"]),
            co_number=int(row["co_number"]) if row["co_number"] is not None else 0,
            stem=row["stem"],
            options=list(opts) if opts else [],
            correct_option=int(row["correct_option"]),
            explanation=row["explanation"],
            marks=float(row["marks"]) if row["marks"] is not None else 1.0,
            difficulty=row["difficulty"] or "medium",
            bloom_level=row["bloom_level"] or "understand",
            status=row["status"] or "draft",
            source=row["source"] or "faculty",
        )

    def _row_to_attempt(self, row: Any) -> QuizAttemptRecord:
        answers = _json_loads(row["answers"])
        return QuizAttemptRecord(
            id=_to_str(row["id"]),
            quiz_id=_to_str(row["quiz_id"]),
            student_id=_to_str(row["student_id"]),
            attempt_number=int(row["attempt_number"]),
            answers=answers or {},
            total_score=float(row["total_score"]) if row["total_score"] is not None else None,
            max_score=float(row["max_score"]) if row["max_score"] is not None else None,
            started_at=row["started_at"] or datetime.now(),
            submitted_at=row["submitted_at"],
        )

    def _row_to_score(self, row: Any) -> StudentCOScoreRecord:
        return StudentCOScoreRecord(
            id=_to_str(row["id"]),
            student_id=_to_str(row["student_id"]),
            subject_id=_to_str(row["subject_id"]),
            module_id=_to_str(row["module_id"]),
            co_id=_to_str(row["co_id"]),
            attempt_id=_to_str(row["attempt_id"]),
            marks_obtained=float(row["marks_obtained"]),
            max_marks=float(row["max_marks"]),
            percentage=float(row["percentage"]) if row["percentage"] is not None else None,
            counted=bool(row["counted"]),
            created_at=row["created_at"] or datetime.now(),
        )

    # -----------------------------------------------------------------
    # QuizStore protocol
    # -----------------------------------------------------------------

    def save_quiz(self, quiz: QuizRecord) -> QuizRecord:
        self.conn.execute(
            text(
                "INSERT INTO quizzes "
                "(id, module_id, subject_id, title, opens_at, closes_at, "
                "published, published_at, created_by, created_at) "
                "VALUES (:id, :mid, :sid, :title, :opens, :closes, "
                ":pub, :pub_at, :cb, :created) "
                "ON CONFLICT (id) DO UPDATE SET "
                "title = EXCLUDED.title, "
                "opens_at = EXCLUDED.opens_at, "
                "closes_at = EXCLUDED.closes_at, "
                "published = EXCLUDED.published, "
                "published_at = EXCLUDED.published_at"
            ),
            {
                "id": str(quiz.id),
                "mid": str(quiz.module_id),
                "sid": str(quiz.subject_id),
                "title": quiz.title,
                "opens": quiz.opens_at,
                "closes": quiz.closes_at,
                "pub": quiz.published,
                "pub_at": quiz.published_at,
                "cb": _to_str(quiz.created_by),
                "created": quiz.created_at,
            },
        )
        # (Re)insert quiz_questions in order
        self.conn.execute(
            text("DELETE FROM quiz_questions WHERE quiz_id = :qid"),
            {"qid": str(quiz.id)},
        )
        for idx, qid in enumerate(quiz.question_ids):
            self.conn.execute(
                text(
                    "INSERT INTO quiz_questions (quiz_id, question_id, position) "
                    "VALUES (:qid, :qid2, :pos) "
                    "ON CONFLICT (quiz_id, question_id) DO UPDATE SET position = EXCLUDED.position"
                ),
                {"qid": str(quiz.id), "qid2": str(qid), "pos": idx},
            )
        return quiz

    def get_quiz(self, quiz_id: str) -> QuizRecord | None:
        row = self.conn.execute(
            text("SELECT * FROM quizzes WHERE id = :id"),
            {"id": str(quiz_id)},
        ).mappings().fetchone()
        if row is None:
            return None
        return self._row_to_quiz(row)

    def list_quizzes(self, subject_id: str) -> list[QuizRecord]:
        rows = self.conn.execute(
            text(
                "SELECT * FROM quizzes "
                "WHERE subject_id = :sid "
                "ORDER BY created_at DESC"
            ),
            {"sid": str(subject_id)},
        ).mappings().fetchall()
        return [self._row_to_quiz(r) for r in rows]

    def get_question(self, question_id: str) -> QuestionRecord | None:
        row = self.conn.execute(
            text(
                "SELECT q.*, co.number AS co_number "
                "FROM questions q "
                "LEFT JOIN course_outcomes co ON co.id = q.co_id "
                "WHERE q.id = :id"
            ),
            {"id": str(question_id)},
        ).mappings().fetchone()
        if row is None:
            return None
        return self._row_to_question(row)

    def get_questions_for_quiz(self, quiz_id: str) -> list[QuestionRecord]:
        rows = self.conn.execute(
            text(
                "SELECT q.*, co.number AS co_number, qq.position "
                "FROM questions q "
                "JOIN quiz_questions qq ON qq.question_id = q.id "
                "LEFT JOIN course_outcomes co ON co.id = q.co_id "
                "WHERE qq.quiz_id = :id "
                "ORDER BY qq.position"
            ),
            {"id": str(quiz_id)},
        ).mappings().fetchall()
        return [self._row_to_question(r) for r in rows]

    def save_attempt(self, attempt: QuizAttemptRecord) -> QuizAttemptRecord:
        existing = self.conn.execute(
            text("SELECT id FROM quiz_attempts WHERE id = :id"),
            {"id": str(attempt.id)},
        ).mappings().fetchone()
        if existing:
            self.conn.execute(
                text(
                    "UPDATE quiz_attempts SET "
                    "quiz_id = :qid, student_id = :sid, "
                    "attempt_number = :an, answers = CAST(:answers AS jsonb), "
                    "total_score = :ts, max_score = :ms, "
                    "started_at = :started, submitted_at = :submitted "
                    "WHERE id = :id"
                ),
                {
                    "id": str(attempt.id),
                    "qid": str(attempt.quiz_id),
                    "sid": str(attempt.student_id),
                    "an": attempt.attempt_number,
                    "answers": json.dumps(attempt.answers),
                    "ts": attempt.total_score,
                    "ms": attempt.max_score,
                    "started": attempt.started_at,
                    "submitted": attempt.submitted_at,
                },
            )
        else:
            try:
                self.conn.execute(
                    text(
                        "INSERT INTO quiz_attempts "
                        "(id, quiz_id, student_id, attempt_number, "
                        "answers, total_score, max_score, "
                        "started_at, submitted_at) "
                        "VALUES (:id, :qid, :sid, :an, "
                        "CAST(:answers AS jsonb), :ts, :ms, :started, :submitted)"
                    ),
                    {
                        "id": str(attempt.id),
                        "qid": str(attempt.quiz_id),
                        "sid": str(attempt.student_id),
                        "an": attempt.attempt_number,
                        "answers": json.dumps(attempt.answers),
                        "ts": attempt.total_score,
                        "ms": attempt.max_score,
                        "started": attempt.started_at,
                        "submitted": attempt.submitted_at,
                    },
                )
            except IntegrityError:
                # DB-level rejection: CHECK (attempt_number IN (1,2)) or
                # UNIQUE (student_id, quiz_id, attempt_number)
                raise AttemptLimitReachedError(
                    "You have used both attempts for this quiz."
                )
        return attempt

    def get_attempt(self, attempt_id: str) -> QuizAttemptRecord | None:
        row = self.conn.execute(
            text("SELECT * FROM quiz_attempts WHERE id = :id"),
            {"id": str(attempt_id)},
        ).mappings().fetchone()
        if row is None:
            return None
        return self._row_to_attempt(row)

    def list_attempts(self, quiz_id: str, student_id: str) -> list[QuizAttemptRecord]:
        rows = self.conn.execute(
            text(
                "SELECT * FROM quiz_attempts "
                "WHERE quiz_id = :qid AND student_id = :sid "
                "ORDER BY attempt_number"
            ),
            {"qid": str(quiz_id), "sid": str(student_id)},
        ).mappings().fetchall()
        return [self._row_to_attempt(r) for r in rows]

    def save_co_scores(self, scores: Sequence[StudentCOScoreRecord]) -> None:
        for s in scores:
            self.conn.execute(
                text(
                    "INSERT INTO student_co_scores "
                    "(id, student_id, subject_id, module_id, co_id, "
                    "attempt_id, marks_obtained, max_marks, percentage, "
                    "counted, created_at) "
                    "VALUES (:id, :sid, :subj, :mid, :cid, "
                    ":aid, :obt, :mx, :pct, :cnt, :created) "
                    "ON CONFLICT (attempt_id, co_id) DO UPDATE SET "
                    "marks_obtained = EXCLUDED.marks_obtained, "
                    "max_marks = EXCLUDED.max_marks, "
                    "percentage = EXCLUDED.percentage, "
                    "counted = EXCLUDED.counted"
                ),
                {
                    "id": str(s.id),
                    "sid": str(s.student_id),
                    "subj": str(s.subject_id),
                    "mid": str(s.module_id),
                    "cid": str(s.co_id),
                    "aid": str(s.attempt_id),
                    "obt": s.marks_obtained,
                    "mx": s.max_marks,
                    "pct": s.percentage,
                    "cnt": s.counted,
                    "created": s.created_at,
                },
            )

    def list_co_scores_for_student(
        self, student_id: str, subject_id: str
    ) -> list[StudentCOScoreRecord]:
        rows = self.conn.execute(
            text(
                "SELECT * FROM student_co_scores "
                "WHERE student_id = :sid AND subject_id = :subj "
                "ORDER BY created_at"
            ),
            {"sid": str(student_id), "subj": str(subject_id)},
        ).mappings().fetchall()
        return [self._row_to_score(r) for r in rows]

    def update_co_score_counted(self, attempt_id: str, counted: bool) -> None:
        self.conn.execute(
            text(
                "UPDATE student_co_scores SET counted = :cnt "
                "WHERE attempt_id = :aid"
            ),
            {"cnt": counted, "aid": str(attempt_id)},
        )
