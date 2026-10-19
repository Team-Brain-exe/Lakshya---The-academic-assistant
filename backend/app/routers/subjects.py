from typing import Optional

from fastapi import APIRouter, Depends, Body, Path
from sqlalchemy import text

from ..db import get_conn
from ..deps import get_current_user, require_faculty
from ..errors import AppError

router = APIRouter(tags=["subjects"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _subject_owned(conn, subject_id: str, faculty_user_id: str):
    """Return the subject row if the faculty owns it, else raise 404."""
    row = conn.execute(
        text("SELECT * FROM subjects WHERE id = :id"),
        {"id": subject_id},
    ).fetchone()
    if row is None or str(row["faculty_user_id"]) != faculty_user_id:
        raise AppError(404, "NOT_FOUND", "Subject not found")
    return row


def _subject_visible(conn, subject_id: str, current_user: dict):
    """Return the subject row if visible to *any* role, else raise 404."""
    row = conn.execute(
        text("SELECT * FROM subjects WHERE id = :id"),
        {"id": subject_id},
    ).fetchone()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Subject not found")
    if current_user["role"] == "faculty":
        if str(row["faculty_user_id"]) != current_user["user_id"]:
            raise AppError(404, "NOT_FOUND", "Subject not found")
    else:
        # Student: must be enrolled
        enrollment = conn.execute(
            text(
                "SELECT 1 FROM enrollments WHERE student_id = :sid AND subject_id = :sid2"
            ),
            {"sid": current_user["student_id"], "sid2": subject_id},
        ).fetchone()
        if enrollment is None:
            raise AppError(404, "NOT_FOUND", "Subject not found")
    return row


def _row_to_subject(row) -> dict:
    return {
        "id": str(row["id"]),
        "code": row["code"],
        "name": row["name"],
        "semester": row["semester"],
        "target_attainment_pct": float(row["target_attainment_pct"]),
        "default_threshold_pct": float(row["default_threshold_pct"]),
        "faculty_user_id": str(row["faculty_user_id"]),
    }


def _row_to_co(row) -> dict:
    return {
        "id": str(row["id"]),
        "subject_id": str(row["subject_id"]),
        "number": row["number"],
        "description": row["description"],
        "threshold_pct": float(row["threshold_pct"]),
        "target_attainment_pct": float(row["target_attainment_pct"]),
    }


# ---------------------------------------------------------------------------
# Subject CRUD
# ---------------------------------------------------------------------------

@router.get("/subjects")
def list_subjects(
    conn=Depends(get_conn),
    current_user=Depends(get_current_user),
):
    uid = current_user["user_id"]
    role = current_user["role"]

    if role == "faculty":
        rows = conn.execute(
            text(
                "SELECT * FROM subjects WHERE faculty_user_id = :uid "
                "ORDER BY code, semester"
            ),
            {"uid": uid},
        ).fetchall()
    else:
        # Student: subjects they are enrolled in
        rows = conn.execute(
            text(
                "SELECT s.* FROM subjects s "
                "JOIN enrollments e ON e.subject_id = s.id "
                "WHERE e.student_id = :sid ORDER BY s.code, s.semester"
            ),
            {"sid": current_user["student_id"]},
        ).fetchall()

    return [_row_to_subject(r) for r in rows]


@router.post("/subjects")
def create_subject(
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    payload: dict = Body(...),
):
    code = payload.get("code")
    name = payload.get("name")
    semester = payload.get("semester")
    target = payload.get("target_attainment_pct", 60)
    threshold = payload.get("default_threshold_pct", 60)

    if not code or not name or semester is None:
        raise AppError(400, "BAD_REQUEST", "code, name and semester are required")

    result = conn.execute(
        text(
            "INSERT INTO subjects (code, name, semester, faculty_user_id, "
            "target_attainment_pct, default_threshold_pct) "
            "VALUES (:code, :name, :sem, :fid, :target, :threshold) "
            "RETURNING *"
        ),
        {
            "code": code,
            "name": name,
            "sem": semester,
            "fid": faculty["user_id"],
            "target": target,
            "threshold": threshold,
        },
    )
    row = result.fetchone()
    return _row_to_subject(row), 201


@router.get("/subjects/{id}")
def get_subject(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    current_user=Depends(get_current_user),
):
    row = _subject_visible(conn, id, current_user)

    cos_rows = conn.execute(
        text("SELECT * FROM course_outcomes WHERE subject_id = :sid ORDER BY number"),
        {"sid": id},
    ).fetchall()

    module_rows = conn.execute(
        text("SELECT * FROM modules WHERE subject_id = :sid ORDER BY number"),
        {"sid": id},
    ).fetchall()

    return {
        **_row_to_subject(row),
        "cos": [_row_to_co(r) for r in cos_rows],
        "modules": [
            {
                "id": str(m["id"]),
                "subject_id": str(m["subject_id"]),
                "number": m["number"],
                "title": m["title"],
                "ppt_file_path": m["ppt_file_path"],
                "processing_status": m["processing_status"],
                "processing_error": m["processing_error"],
                "processed_at": m["processed_at"].isoformat() if m["processed_at"] else None,
            }
            for m in module_rows
        ],
    }


@router.patch("/subjects/{id}")
def update_subject(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    payload: dict = Body(...),
):
    row = _subject_owned(conn, id, faculty["user_id"])

    updates = {}
    for field in ("code", "name", "semester", "target_attainment_pct", "default_threshold_pct"):
        if field in payload:
            updates[field] = payload[field]

    if not updates:
        return _row_to_subject(row)

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    params = dict(updates)
    params["id"] = id
    params["fid"] = faculty["user_id"]

    result = conn.execute(
        text(
            f"UPDATE subjects SET {set_clause} "
            "WHERE id = :id AND faculty_user_id = :fid RETURNING *"
        ),
        params,
    )
    row = result.fetchone()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Subject not found")
    return _row_to_subject(row)


@router.delete("/subjects/{id}")
def delete_subject(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    result = conn.execute(
        text(
            "DELETE FROM subjects WHERE id = :id AND faculty_user_id = :fid"
        ),
        {"id": id, "fid": faculty["user_id"]},
    )
    if result.rowcount == 0:
        raise AppError(404, "NOT_FOUND", "Subject not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# COs
# ---------------------------------------------------------------------------

@router.get("/subjects/{id}/cos")
def list_cos(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    _subject_owned(conn, id, faculty["user_id"])
    rows = conn.execute(
        text("SELECT * FROM course_outcomes WHERE subject_id = :sid ORDER BY number"),
        {"sid": id},
    ).fetchall()
    return [_row_to_co(r) for r in rows]


@router.put("/subjects/{id}/cos")
def upsert_cos(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    payload: dict = Body(...),
):
    """Upsert COs by number (1..6), in one transaction."""
    _subject_owned(conn, id, faculty["user_id"])

    cos = payload.get("cos")
    if not isinstance(cos, list):
        raise AppError(400, "BAD_REQUEST", "Expected a 'cos' array")

    result_rows = []
    for co in cos:
        number = co.get("number")
        description = co.get("description")
        threshold = co.get("threshold_pct", 60)
        target = co.get("target_attainment_pct", 60)

        if number is None or not (1 <= number <= 6):
            raise AppError(
                422, "VALIDATION_ERROR",
                f"CO number must be between 1 and 6",
                details={"field": "number", "value": number},
            )
        if not description:
            raise AppError(
                400, "BAD_REQUEST",
                f"CO {number}: description is required",
            )

        result = conn.execute(
            text(
                "INSERT INTO course_outcomes (subject_id, number, description, "
                "threshold_pct, target_attainment_pct) "
                "VALUES (:sid, :num, :desc, :thresh, :target) "
                "ON CONFLICT (subject_id, number) DO UPDATE SET "
                "description = EXCLUDED.description, "
                "threshold_pct = EXCLUDED.threshold_pct, "
                "target_attainment_pct = EXCLUDED.target_attainment_pct "
                "RETURNING *"
            ),
            {
                "sid": id,
                "num": number,
                "desc": description,
                "thresh": threshold,
                "target": target,
            },
        )
        row = result.fetchone()
        result_rows.append(_row_to_co(row))

    # Return only the COs for this subject, ordered by number
    return sorted(result_rows, key=lambda c: c["number"])
