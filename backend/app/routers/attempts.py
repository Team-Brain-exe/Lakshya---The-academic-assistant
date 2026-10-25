"""Quiz attempt endpoints.

Section 7 of docs/api-contract.md (Part A):
- POST /quizzes/{id}/attempts  (student — start)
- GET  /attempts/{id}          (student — resume)
- PUT  /attempts/{id}/answers  (student — autosave draft)
- POST /attempts/{id}/submit   (student — submit + grade)
- GET  /attempts/{id}/review   (student — review own submitted attempt)

Each route builds a PostgresQuizStore from the request connection, wraps it
in a QuizRouterHandler, delegates to the handler, then commits on success
or rolls back on error.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Path
from fastapi.responses import JSONResponse

from app.db import get_conn
from app.deps import get_current_user, require_student
from app.routers.quizzes import QuizRouterHandler
from app.stores.postgres_quiz_store import PostgresQuizStore

router = APIRouter(tags=["quizzes"])


def _make_handler(conn) -> QuizRouterHandler:
    """Factory: PostgresQuizStore + QuizRouterHandler from a DB connection."""
    return QuizRouterHandler(PostgresQuizStore(conn), calendar_store=None)


@router.post("/quizzes/{id}/attempts")
def start_attempt(
    id: str = Path(..., alias="id"),
    current_user: dict = Depends(require_student),
    conn=Depends(get_conn),
):
    """Student starts a quiz attempt. Returns masked questions (no correct_option)."""
    handler = _make_handler(conn)
    status_code, body = handler.start_attempt(current_user, id)
    if status_code < 400:
        conn.commit()
    else:
        conn.rollback()
    return JSONResponse(status_code=status_code, content=body)


@router.get("/attempts/{id}")
def get_attempt_state(
    id: str = Path(..., alias="id"),
    current_user: dict = Depends(require_student),
    conn=Depends(get_conn),
):
    """Student resumes an in-progress attempt via refresh. Questions stay masked."""
    handler = _make_handler(conn)
    status_code, body = handler.get_attempt_state(current_user, id)
    if status_code < 400:
        conn.commit()
    else:
        conn.rollback()
    return JSONResponse(status_code=status_code, content=body)


@router.put("/attempts/{id}/answers")
def save_answers(
    id: str = Path(..., alias="id"),
    payload: dict = Body(..., embed=False),
    current_user: dict = Depends(require_student),
    conn=Depends(get_conn),
):
    """Student autosaves draft answers for their own attempt."""
    answers = payload.get("answers", {})
    handler = _make_handler(conn)
    status_code, body = handler.save_answers(current_user, id, answers)
    if status_code < 400:
        conn.commit()
    else:
        conn.rollback()
    return JSONResponse(status_code=status_code, content=body)


@router.post("/attempts/{id}/submit")
def submit_attempt(
    id: str = Path(..., alias="id"),
    payload: dict = Body(..., embed=False),
    current_user: dict = Depends(require_student),
    conn=Depends(get_conn),
):
    """Student submits answers. Returns deterministic grade + writes student_co_scores."""
    answers = payload.get("answers", {})
    handler = _make_handler(conn)
    status_code, body = handler.submit(current_user, id, answers)
    if status_code < 400:
        conn.commit()
    else:
        conn.rollback()
    return JSONResponse(status_code=status_code, content=body)


@router.get("/attempts/{id}/review")
def review_attempt(
    id: str = Path(..., alias="id"),
    current_user: dict = Depends(require_student),
    conn=Depends(get_conn),
):
    """Student reviews their own submitted attempt (reveals correct_option + explanation)."""
    handler = _make_handler(conn)
    status_code, body = handler.review(current_user, id)
    if status_code < 400:
        conn.commit()
    else:
        conn.rollback()
    return JSONResponse(status_code=status_code, content=body)
