"""Minimal quizzes router to support the QUESTION_NOT_APPROVED test.

The full quiz/attempt endpoints belong to Arya (contract section 7).
This file provides just enough to exercise the database approval triggers.
"""
from fastapi import APIRouter, Depends, Body, Path
from sqlalchemy import text

from ..db import get_conn
from ..deps import require_faculty
from ..errors import AppError

router = APIRouter(tags=["quizzes"])


def _row_to_quiz(row) -> dict:
    return {
        "id": str(row["id"]),
        "module_id": str(row["module_id"]) if row["module_id"] else None,
        "subject_id": str(row["subject_id"]),
        "title": row["title"],
        "opens_at": row["opens_at"].isoformat() if row["opens_at"] else None,
        "closes_at": row["closes_at"].isoformat() if row["closes_at"] else None,
        "published": bool(row["published"]),
        "published_at": row["published_at"].isoformat() if row["published_at"] else None,
        "question_count": row["question_count"],
    }


@router.post("/quizzes")
def create_quiz(
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    payload: dict = Body(...),
):
    module_id = payload.get("module_id")
    title = payload.get("title")
    question_ids = payload.get("question_ids", [])
    opens_at = payload.get("opens_at")
    closes_at = payload.get("closes_at")

    if not module_id or not title:
        raise AppError(400, "BAD_REQUEST", "module_id and title are required")

    # Verify faculty owns the subject that owns the module
    mod = conn.execute(
        text(
            "SELECT m.id, m.subject_id FROM modules m "
            "JOIN subjects s ON s.id = m.subject_id "
            "WHERE m.id = :mid AND s.faculty_user_id = :fid"
        ),
        {"mid": str(module_id), "fid": faculty["user_id"]},
    ).fetchone()
    if mod is None:
        raise AppError(404, "NOT_FOUND", "Module not found")
    subject_id = str(mod["subject_id"])

    # Create quiz
    result = conn.execute(
        text(
            "INSERT INTO quizzes (module_id, subject_id, title, opens_at, closes_at, "
            "created_by) VALUES (:mid, :sid, :title, :opens, :closes, :cb) RETURNING *"
        ),
        {
            "mid": str(module_id),
            "sid": subject_id,
            "title": title,
            "opens": opens_at,
            "closes": closes_at,
            "cb": faculty["user_id"],
        },
    )
    quiz_row = result.fetchone()
    quiz_id = str(quiz_row["id"])

    # Insert quiz_questions (trigger will reject unapproved questions)
    for idx, qid in enumerate(question_ids):
        conn.execute(
            text(
                "INSERT INTO quiz_questions (quiz_id, question_id, position) "
                "VALUES (:qid, :qid2, :pos)"
            ),
            {"qid": quiz_id, "qid2": str(qid), "pos": idx},
        )

    # Count questions
    count = conn.execute(
        text("SELECT COUNT(*) AS c FROM quiz_questions WHERE quiz_id = :qid"),
        {"qid": quiz_id},
    ).fetchone()

    result = conn.execute(
        text("SELECT * FROM quizzes WHERE id = :id"),
        {"id": quiz_id},
    ).fetchone()
    # Build response with question_count
    quiz_dict = _row_to_quiz(result)
    quiz_dict["question_count"] = count["c"]
    return quiz_dict, 201


@router.post("/quizzes/{id}/questions")
def add_quiz_question(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    payload: dict = Body(...),
):
    question_id = payload.get("question_id")
    if not question_id:
        raise AppError(400, "BAD_REQUEST", "question_id is required")

    # Verify faculty owns the subject that owns the quiz
    quiz = conn.execute(
        text(
            "SELECT q.* FROM quizzes q "
            "JOIN subjects s ON s.id = q.subject_id "
            "WHERE q.id = :id AND s.faculty_user_id = :fid"
        ),
        {"id": id, "fid": faculty["user_id"]},
    ).fetchone()
    if quiz is None:
        raise AppError(404, "NOT_FOUND", "Quiz not found")

    # This insert triggers fn_quiz_question_must_be_approved if the question
    # is not approved
    conn.execute(
        text(
            "INSERT INTO quiz_questions (quiz_id, question_id, position) "
            "VALUES (:qid, :qid2, :pos)"
        ),
        {"qid": id, "qid2": str(question_id), "pos": 0},
    )
    return {"added": True, "question_id": str(question_id)}


@router.post("/quizzes/{id}/publish")
def publish_quiz(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    # Verify ownership
    quiz = conn.execute(
        text(
            "SELECT q.* FROM quizzes q "
            "JOIN subjects s ON s.id = q.subject_id "
            "WHERE q.id = :id AND s.faculty_user_id = :fid"
        ),
        {"id": id, "fid": faculty["user_id"]},
    ).fetchone()
    if quiz is None:
        raise AppError(404, "NOT_FOUND", "Quiz not found")

    # Set published = true; trigger fn_quiz_publish_check fires if any
    # question is unapproved or no questions exist
    result = conn.execute(
        text(
            "UPDATE quizzes SET published = true, published_at = now() "
            "WHERE id = :id RETURNING *"
        ),
        {"id": id},
    )
    published = result.fetchone()

    # Create an event for the quiz
    event_result = conn.execute(
        text(
            "INSERT INTO events (subject_id, type, title, starts_at, quiz_id, created_by, "
            "created_by_agent) VALUES (:sid, 'quiz', :title, :starts, :qid, :cb, false) RETURNING id"
        ),
        {
            "sid": str(published["subject_id"]),
            "title": published["title"],
            "starts": published["opens_at"],
            "qid": id,
            "cb": faculty["user_id"],
        },
    )
    event_id = str(event_result.fetchone()["id"])

    count = conn.execute(
        text("SELECT COUNT(*) AS c FROM quiz_questions WHERE quiz_id = :qid"),
        {"qid": id},
    ).fetchone()

    quiz_dict = _row_to_quiz(published)
    quiz_dict["question_count"] = count["c"]
    quiz_dict["event_id"] = event_id
    return quiz_dict
