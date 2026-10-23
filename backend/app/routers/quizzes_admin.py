"""Minimal quizzes router to support the QUESTION_NOT_APPROVED test.

The full quiz/attempt endpoints belong to Arya (contract section 7).
This file provides just enough to exercise the database approval triggers.
"""
from fastapi import APIRouter, Depends, Body, Path, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ..db import get_conn
from ..deps import require_faculty, get_current_user
from ..errors import AppError
from ..engine.settings import load_grading_settings

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
    ).mappings().fetchone()
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
    quiz_row = result.mappings().fetchone()
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
    ).mappings().fetchone()

    result = conn.execute(
        text("SELECT * FROM quizzes WHERE id = :id"),
        {"id": quiz_id},
    ).mappings().fetchone()
    # Build response with question_count
    quiz_dict = _row_to_quiz(result)
    quiz_dict["question_count"] = count["c"]
    return JSONResponse(content=quiz_dict, status_code=201)


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
    ).mappings().fetchone()
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
    ).mappings().fetchone()
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
    published = result.mappings().fetchone()

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
    event_id = str(event_result.mappings().fetchone()["id"])

    count = conn.execute(
        text("SELECT COUNT(*) AS c FROM quiz_questions WHERE quiz_id = :qid"),
        {"qid": id},
    ).mappings().fetchone()

    quiz_dict = _row_to_quiz(published)
    quiz_dict["question_count"] = count["c"]
    quiz_dict["event_id"] = event_id
    return quiz_dict


# ---------------------------------------------------------------------------
# Quiz listing & retrieval
# ---------------------------------------------------------------------------


def _quiz_visible_query(current_user: dict, module_id: str | None,
                       subject_id: str | None) -> tuple[str, dict]:
    """Build the WHERE clause / params for listing quizzes visible to the
    current user.

    Faculty see all quizzes for subjects they own.
    Students see only *published* quizzes for subjects they are enrolled in.
    """
    role = current_user["role"]
    clauses = []
    params: dict = {}

    if role == "faculty":
        clauses.append("s.faculty_user_id = :uid")
        params["uid"] = current_user["user_id"]
    else:
        clauses.append("e.student_id = :sid")
        params["sid"] = current_user["student_id"]
        clauses.append("q.published = true")

    if subject_id:
        clauses.append("q.subject_id = :subject_id")
        params["subject_id"] = str(subject_id)
    if module_id:
        clauses.append("q.module_id = :module_id")
        params["module_id"] = str(module_id)

    where = " AND ".join(clauses)

    if role == "faculty":
        sql = (
            "SELECT q.*, COUNT(qq.question_id) AS question_count "
            "FROM quizzes q "
            "JOIN subjects s ON s.id = q.subject_id "
            f"LEFT JOIN quiz_questions qq ON qq.quiz_id = q.id "
            f"WHERE {where} "
            "GROUP BY q.id ORDER BY q.created_at DESC"
        )
    else:
        sql = (
            "SELECT q.*, COUNT(DISTINCT qq.question_id) AS question_count, "
            "(SELECT COUNT(*) FROM quiz_attempts qa "
            "WHERE qa.quiz_id = q.id AND qa.student_id = :sid) AS attempt_count "
            "FROM quizzes q "
            "JOIN enrollments e ON e.subject_id = q.subject_id "
            f"LEFT JOIN quiz_questions qq ON qq.quiz_id = q.id "
            f"WHERE {where} "
            "GROUP BY q.id ORDER BY q.created_at DESC"
        )

    return sql, params


@router.get("/quizzes")
def list_quizzes(
    conn=Depends(get_conn),
    current_user=Depends(get_current_user),
    module_id: str | None = Query(default=None),
    subject_id: str | None = Query(default=None),
):
    """List quizzes visible to the current user.

    Faculty see all quizzes for their subjects.
    Students see only *published* quizzes for subjects they are enrolled in.
    """
    sql, params = _quiz_visible_query(current_user, module_id, subject_id)
    rows = conn.execute(text(sql), params).mappings().fetchall()
    max_att = load_grading_settings().max_attempts
    results = []
    for r in rows:
        item = _row_to_quiz(r) | {"question_count": r["question_count"]}
        if current_user["role"] == "student":
            attempt_count = r["attempt_count"]
            item["attempts_used"] = attempt_count or 0
            item["attempts_left"] = max(0, max_att - (attempt_count or 0))
        results.append(item)
    return results


@router.get("/quizzes/{id}")
def get_quiz(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    current_user=Depends(get_current_user),
):
    """Get a single quiz by ID.

    Faculty can see any quiz in their subjects.
    Students can only see *published* quizzes for subjects they are enrolled in.
    """
    role = current_user["role"]
    if role == "faculty":
        row = conn.execute(
            text(
                "SELECT q.*, COUNT(qq.question_id) AS question_count "
                "FROM quizzes q "
                "JOIN subjects s ON s.id = q.subject_id "
                "LEFT JOIN quiz_questions qq ON qq.quiz_id = q.id "
                "WHERE q.id = :id AND s.faculty_user_id = :fid "
                "GROUP BY q.id"
            ),
            {"id": str(id), "fid": current_user["user_id"]},
        ).mappings().fetchone()
    else:
        row = conn.execute(
            text(
                "SELECT q.*, COUNT(qq.question_id) AS question_count "
                "FROM quizzes q "
                "JOIN enrollments e ON e.subject_id = q.subject_id "
                "LEFT JOIN quiz_questions qq ON qq.quiz_id = q.id "
                "WHERE q.id = :id AND e.student_id = :sid AND q.published = true "
                "GROUP BY q.id"
            ),
            {"id": str(id), "sid": current_user["student_id"]},
        ).mappings().fetchone()

    if row is None:
        raise AppError(404, "NOT_FOUND", "Quiz not found")
    return _row_to_quiz(row) | {"question_count": row["question_count"]}
