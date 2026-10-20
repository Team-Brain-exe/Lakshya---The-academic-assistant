from fastapi import APIRouter, Depends, Body, Path
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ..db import get_conn
from ..deps import require_faculty
from ..errors import AppError

router = APIRouter(tags=["modules"])


def _row_to_module(row) -> dict:
    return {
        "id": str(row["id"]),
        "subject_id": str(row["subject_id"]),
        "number": row["number"],
        "title": row["title"],
        "ppt_file_path": row["ppt_file_path"],
        "processing_status": row["processing_status"],
        "processing_error": row["processing_error"],
        "processed_at": row["processed_at"].isoformat() if row["processed_at"] else None,
    }


def _module_owned(conn, module_id: str, faculty_user_id: str):
    """Return the module row if it belongs to a subject the faculty owns."""
    row = conn.execute(
        text(
            "SELECT m.* FROM modules m "
            "JOIN subjects s ON s.id = m.subject_id "
            "WHERE m.id = :id AND s.faculty_user_id = :fid"
        ),
        {"id": module_id, "fid": faculty_user_id},
    ).mappings().fetchone()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Module not found")
    return row


@router.post("/subjects/{id}/modules")
def create_module(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    payload: dict = Body(...),
):
    # Verify faculty owns the subject
    subj = conn.execute(
        text("SELECT id FROM subjects WHERE id = :id AND faculty_user_id = :fid"),
        {"id": id, "fid": faculty["user_id"]},
    ).mappings().fetchone()
    if subj is None:
        raise AppError(404, "NOT_FOUND", "Subject not found")

    number = payload.get("number")
    title = payload.get("title")
    if number is None or not title:
        raise AppError(400, "BAD_REQUEST", "number and title are required")

    result = conn.execute(
        text(
            "INSERT INTO modules (subject_id, number, title) "
            "VALUES (:sid, :num, :title) RETURNING *"
        ),
        {"sid": id, "num": number, "title": title},
    )
    row = result.mappings().fetchone()
    return JSONResponse(content=_row_to_module(row), status_code=201)


@router.patch("/modules/{id}")
def update_module(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    payload: dict = Body(...),
):
    row = _module_owned(conn, id, faculty["user_id"])

    updates = {}
    for field in ("number", "title", "ppt_file_path",
                  "processing_status", "processing_error"):
        if field in payload:
            updates[field] = payload[field]

    if not updates:
        return _row_to_module(row)

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    params = dict(updates)
    params["id"] = id
    params["fid"] = faculty["user_id"]

    result = conn.execute(
        text(
            f"UPDATE modules SET {set_clause} "
            "FROM subjects s "
            "WHERE modules.id = :id AND modules.subject_id = s.id "
            "AND s.faculty_user_id = :fid RETURNING modules.*"
        ),
        params,
    )
    row = result.mappings().fetchone()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Module not found")
    return _row_to_module(row)


@router.delete("/modules/{id}")
def delete_module(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
):
    result = conn.execute(
        text(
            "DELETE FROM modules m USING subjects s "
            "WHERE m.id = :id AND m.subject_id = s.id AND s.faculty_user_id = :fid"
        ),
        {"id": id, "fid": faculty["user_id"]},
    )
    if result.rowcount == 0:
        raise AppError(404, "NOT_FOUND", "Module not found")
    return {"deleted": True}
