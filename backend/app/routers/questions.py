import json

from fastapi import APIRouter, Depends, Body, Path, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ..db import get_conn
from ..deps import require_faculty
from ..errors import AppError

router = APIRouter(tags=["questions"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_question(row) -> dict:
    return {
        "id": str(row["id"]),
        "module_id": str(row["module_id"]),
        "co_id": str(row["co_id"]),
        "co_number": row["co_number"],
        "stem": row["stem"],
        "options": list(row["options"]),
        "correct_option": row["correct_option"],
        "explanation": row["explanation"],
        "marks": float(row["marks"]) if row["marks"] else None,
        "difficulty": row["difficulty"],
        "bloom_level": row["bloom_level"],
        "status": row["status"],
        "source": row["source"],
        "created_by": str(row["created_by"]) if row["created_by"] else None,
    }


def _validate_module_and_co(conn, module_id: str, co_id: str, faculty_user_id: str):
    """Verify the module and CO exist, belong to the same subject, and the
    faculty owns that subject. Raises 404 on any failure."""
    stmt = text(
        "SELECT m.subject_id AS subject_id "
        "FROM modules m WHERE m.id = :mid"
    )
    mod = conn.execute(stmt, {"mid": str(module_id)}).mappings().fetchone()
    if mod is None:
        raise AppError(404, "NOT_FOUND", "Module not found")

    # Check faculty owns the subject
    owner = conn.execute(
        text(
            "SELECT 1 FROM subjects s WHERE s.id = :sid AND s.faculty_user_id = :fid"
        ),
        {"sid": str(mod["subject_id"]), "fid": faculty_user_id},
    ).mappings().fetchone()
    if owner is None:
        raise AppError(404, "NOT_FOUND", "Module not found")

    # Check CO belongs to the same subject
    co = conn.execute(
        text(
            "SELECT id, number FROM course_outcomes "
            "WHERE id = :cid AND subject_id = :sid"
        ),
        {"cid": str(co_id), "sid": str(mod["subject_id"])},
    ).mappings().fetchone()
    if co is None:
        raise AppError(404, "NOT_FOUND", "CO not found or does not belong to the module's subject")
    return co


def _question_owned(conn, question_id: str, faculty_user_id: str):
    """Return the question row (with co_number) if the faculty owns the
    subject it belongs to, else raise 404."""
    row = conn.execute(
        text(
            "SELECT q.*, co.number AS co_number FROM questions q "
            "JOIN modules m ON m.id = q.module_id "
            "JOIN subjects s ON s.id = m.subject_id "
            "LEFT JOIN course_outcomes co ON co.id = q.co_id "
            "WHERE q.id = :qid AND s.faculty_user_id = :fid"
        ),
        {"qid": str(question_id), "fid": faculty_user_id},
    ).mappings().fetchone()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Question not found")
    return row


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/questions")
def list_questions(
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    module_id: str = Query(...),
    co_id: str | None = Query(None),
    status: str | None = Query(None),
    source: str | None = Query(None),
):
    # Verify faculty owns the subject of this module
    mod = conn.execute(
        text(
            "SELECT m.id FROM modules m "
            "JOIN subjects s ON s.id = m.subject_id "
            "WHERE m.id = :mid AND s.faculty_user_id = :fid"
        ),
        {"mid": str(module_id), "fid": faculty["user_id"]},
    ).mappings().fetchone()
    if mod is None:
        raise AppError(404, "NOT_FOUND", "Module not found")

    where = ["q.module_id = :mid"]
    params: dict = {"mid": str(module_id)}
    if co_id:
        where.append("q.co_id = :cid")
        params["cid"] = str(co_id)
    if status:
        where.append("q.status = :status")
        params["status"] = status
    if source:
        where.append("q.source = :src")
        params["src"] = source

    rows = conn.execute(
        text(
            "SELECT q.*, co.number AS co_number FROM questions q "
            "LEFT JOIN course_outcomes co ON co.id = q.co_id "
            "WHERE " + " AND ".join(where) + " ORDER BY q.created_at"
        ),
        params,
    ).mappings().fetchall()
    return [_row_to_question(r) for r in rows]


@router.post("/questions")
def create_question(
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    payload: dict = Body(...),
):
    module_id = payload.get("module_id")
    co_id = payload.get("co_id")
    stem = payload.get("stem")
    options = payload.get("options")
    correct_option = payload.get("correct_option")

    if module_id is None or co_id is None:
        raise AppError(400, "BAD_REQUEST", "module_id and co_id are required")
    if not stem or not options or correct_option is None:
        raise AppError(400, "BAD_REQUEST", "stem, options and correct_option are required")

    # Validate module + CO ownership
    _validate_module_and_co(conn, module_id, co_id, faculty["user_id"])

    result = conn.execute(
        text(
            "INSERT INTO questions "
            "(module_id, co_id, stem, options, correct_option, explanation, "
            "marks, difficulty, bloom_level, source, created_by) "
            "VALUES "
            "(:module_id, :co_id, :stem, CAST(:opts AS jsonb), :correct_option, :explanation, "
            ":marks, :difficulty, :bloom_level, 'faculty', :created_by) "
            "RETURNING * "
            "-- co_number join"
        ),
        {
            "module_id": str(module_id),
            "co_id": str(co_id),
            "stem": stem,
            "opts": json.dumps(options),
            "correct_option": correct_option,
            "explanation": payload.get("explanation"),
            "marks": payload.get("marks", 1),
            "difficulty": payload.get("difficulty"),
            "bloom_level": payload.get("bloom_level"),
            "created_by": faculty["user_id"],
        },
    )
    row = result.mappings().fetchone()

    # Re-fetch with co_number join
    full = conn.execute(
        text(
            "SELECT q.*, co.number AS co_number FROM questions q "
            "LEFT JOIN course_outcomes co ON co.id = q.co_id "
            "WHERE q.id = :id"
        ),
        {"id": str(row["id"])},
    ).mappings().fetchone()
    return JSONResponse(content=_row_to_question(full), status_code=201)


@router.post("/questions/batch")
def create_questions_batch(
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    payload: dict = Body(...),
):
    questions = payload.get("questions")
    if not isinstance(questions, list) or len(questions) == 0:
        raise AppError(400, "BAD_REQUEST", "Expected a non-empty 'questions' array")

    created = []
    for q in questions:
        module_id = q.get("module_id")
        co_id = q.get("co_id")
        if module_id is None or co_id is None:
            raise AppError(400, "BAD_REQUEST", "Each question needs module_id and co_id")
        _validate_module_and_co(conn, module_id, co_id, faculty["user_id"])

        result = conn.execute(
            text(
                "INSERT INTO questions "
                "(module_id, co_id, stem, options, correct_option, explanation, "
                "marks, difficulty, bloom_level, source, created_by) "
                "VALUES "
                "(:module_id, :co_id, :stem, CAST(:opts AS jsonb), :correct_option, :explanation, "
                ":marks, :difficulty, :bloom_level, 'AI', :created_by) "
                "RETURNING id"
            ),
            {
                "module_id": str(module_id),
                "co_id": str(co_id),
                "stem": q.get("stem"),
                "opts": json.dumps(q.get("options")),
                "correct_option": q.get("correct_option"),
                "explanation": q.get("explanation"),
                "marks": q.get("marks", 1),
                "difficulty": q.get("difficulty"),
                "bloom_level": q.get("bloom_level"),
                "created_by": faculty["user_id"],
            },
        )
        qid = str(result.mappings().fetchone()["id"])
        created.append(qid)

    # Fetch all created questions with co_number
    placeholders = ", ".join(f"'{q}'" for q in created)
    rows = conn.execute(
        text(
            "SELECT q.*, co.number AS co_number FROM questions q "
            "LEFT JOIN course_outcomes co ON co.id = q.co_id "
            "WHERE q.id IN (" + placeholders + ") ORDER BY q.created_at"
        ),
    ).mappings().fetchall()
    return JSONResponse(content=[_row_to_question(r) for r in rows], status_code=201)


@router.patch("/questions/{id}")
def update_question(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    payload: dict = Body(...),
):
    row = _question_owned(conn, id, faculty["user_id"])

    updatable = {"stem", "options", "correct_option", "explanation",
                 "marks", "difficulty", "bloom_level", "co_id", "module_id",
                 "status", "source"}
    updates = {k: v for k, v in payload.items() if k in updatable}

    if not updates:
        return _row_to_question(row)

    # If co_id is being updated, validate it belongs to the module's subject
    if "co_id" in updates:
        qrow = conn.execute(
            text("SELECT module_id FROM questions WHERE id = :id"),
            {"id": id},
        ).mappings().fetchone()
        _validate_module_and_co(conn, str(qrow["module_id"]), str(updates["co_id"]),
                                faculty["user_id"])

    # Build SET clause, handling jsonb columns
    set_parts = []
    params = {}
    for k, v in updates.items():
        if k == "options":
            set_parts.append("options = CAST(:opts AS jsonb)")
            params["opts"] = json.dumps(v) if not isinstance(v, str) else v
        else:
            set_parts.append(f"{k} = :{k}")
            params[k] = v
    set_clause = ", ".join(set_parts)
    params["id"] = id
    params["fid"] = faculty["user_id"]

    result = conn.execute(
        text(
            f"UPDATE questions SET {set_clause} "
            "FROM modules m JOIN subjects s ON s.id = m.subject_id "
            "WHERE questions.id = :id AND m.id = questions.module_id "
            "AND s.faculty_user_id = :fid "
            "RETURNING questions.*"
        ),
        params,
    )
    updated = result.mappings().fetchone()
    if updated is None:
        raise AppError(404, "NOT_FOUND", "Question not found")

    # Re-fetch with co_number
    full = conn.execute(
        text(
            "SELECT q.*, co.number AS co_number FROM questions q "
            "LEFT JOIN course_outcomes co ON co.id = q.co_id "
            "WHERE q.id = :id"
        ),
        {"id": id},
    ).mappings().fetchone()
    return _row_to_question(full)


@router.post("/questions/{id}/approve")
def approve_question(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    row = _question_owned(conn, id, faculty["user_id"])
    result = conn.execute(
        text("UPDATE questions SET status = 'approved' WHERE id = :id RETURNING *"),
        {"id": id},
    )
    updated = result.mappings().fetchone()
    full = conn.execute(
        text(
            "SELECT q.*, co.number AS co_number FROM questions q "
            "LEFT JOIN course_outcomes co ON co.id = q.co_id "
            "WHERE q.id = :id"
        ),
        {"id": id},
    ).mappings().fetchone()
    return _row_to_question(full)


@router.post("/questions/{id}/reject")
def reject_question(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    row = _question_owned(conn, id, faculty["user_id"])
    conn.execute(
        text("UPDATE questions SET status = 'rejected' WHERE id = :id"),
        {"id": id},
    )
    full = conn.execute(
        text(
            "SELECT q.*, co.number AS co_number FROM questions q "
            "LEFT JOIN course_outcomes co ON co.id = q.co_id "
            "WHERE q.id = :id"
        ),
        {"id": id},
    ).mappings().fetchone()
    return _row_to_question(full)
