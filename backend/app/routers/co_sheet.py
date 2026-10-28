"""CO Sheet, summary, drilldown, weak-CO, export, and student progress endpoints.

Section 8 of docs/api-contract.md:
- GET /subjects/{id}/co-sheet
- GET /subjects/{id}/co-summary
- GET /subjects/{id}/cos/{co_id}/drilldown
- GET /subjects/{id}/weak-cos
- GET /subjects/{id}/co-sheet/export
- GET /students/me/progress
- GET /students/{usn}/progress
"""

from __future__ import annotations

from typing import Any

from app.services.co_analytics import (
    AnalyticsStore,
    export_co_sheet_excel,
    get_class_summary_data,
    get_co_drilldown_data,
    get_co_sheet_data,
    get_student_progress_data,
    get_weak_cos_data,
)
from app.services.quizzes import ForbiddenError, NotFoundError

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


def format_error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


class COSheetRouterHandler:
    def __init__(self, store: AnalyticsStore) -> None:
        self.store = store

    def get_sheet(
        self,
        current_user: dict[str, Any],
        subject_id: str,
        scope: str = "semester",
        module_id: str | None = None,
        section: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        if current_user.get("role") != "faculty":
            return 403, format_error("FORBIDDEN", "Only faculty can view the full CO sheet.")

        res = get_co_sheet_data(
            self.store,
            subject_id=subject_id,
            scope=scope,
            module_id=module_id,
            section=section,
        )
        return 200, res

    def get_summary(
        self,
        current_user: dict[str, Any],
        subject_id: str,
        section: str | None = None,
    ) -> tuple[int, Any]:
        if current_user.get("role") != "faculty":
            return 403, format_error("FORBIDDEN", "Only faculty can view the class CO summary.")

        res = get_class_summary_data(self.store, subject_id, section=section)
        return 200, res

    def get_drilldown(
        self,
        current_user: dict[str, Any],
        subject_id: str,
        co_id: str,
        module_id: str | None = None,
        section: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        if current_user.get("role") != "faculty":
            return 403, format_error("FORBIDDEN", "Only faculty can view CO drill-down data.")

        try:
            res = get_co_drilldown_data(
                self.store,
                subject_id=subject_id,
                co_id=co_id,
                module_id=module_id,
                section=section,
            )
            return 200, res
        except NotFoundError as exc:
            return 404, format_error("NOT_FOUND", str(exc))

    def get_weak_cos(
        self,
        current_user: dict[str, Any],
        subject_id: str,
        section: str | None = None,
    ) -> tuple[int, Any]:
        if current_user.get("role") != "faculty":
            return 403, format_error("FORBIDDEN", "Only faculty can view weak COs.")

        res = get_weak_cos_data(self.store, subject_id, section=section)
        return 200, res

    def export_excel(
        self,
        current_user: dict[str, Any],
        subject_id: str,
        scope: str = "semester",
        module_id: str | None = None,
        section: str | None = None,
    ) -> tuple[int, bytes | dict[str, Any], dict[str, str]]:
        if current_user.get("role") != "faculty":
            return 403, format_error("FORBIDDEN", "Only faculty can export the CO sheet."), {}

        xlsx_bytes = export_co_sheet_excel(
            self.store,
            subject_id=subject_id,
            scope=scope,
            module_id=module_id,
            section=section,
        )
        headers = {
            "Content-Disposition": f'attachment; filename="co_sheet_{subject_id}.xlsx"',
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        return 200, xlsx_bytes, headers

    def get_progress(
        self,
        current_user: dict[str, Any],
        usn: str,
        subject_id: str,
    ) -> tuple[int, dict[str, Any]]:
        try:
            res = get_student_progress_data(
                self.store,
                current_user=current_user,
                usn=usn,
                subject_id=subject_id,
            )
            return 200, res
        except ForbiddenError as exc:
            return 403, format_error("FORBIDDEN", str(exc))
        except NotFoundError as exc:
            return 404, format_error("NOT_FOUND", str(exc))


# ---------------------------------------------------------------------------
# Live routes (Postgres)
# ---------------------------------------------------------------------------

from sqlalchemy import text

from ..db import get_conn
from ..deps import get_current_user, require_faculty
from ..errors import AppError
from ..pg.analytics import PostgresAnalyticsStore
from ..pg.common import as_uuid, subject_for_faculty, subject_for_student

router = APIRouter(tags=["co-sheet"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _check_scope(conn, subject_id: str, scope: str, module_id: str | None) -> str | None:
    if scope not in ("module", "semester"):
        raise AppError(422, "VALIDATION_ERROR", "scope must be 'module' or 'semester'")
    if scope == "module":
        if not module_id:
            raise AppError(400, "BAD_REQUEST", "module_id is required when scope=module")
        row = conn.execute(
            text("SELECT 1 FROM modules WHERE id = :m AND subject_id = :s"),
            {"m": as_uuid(module_id, "Module"), "s": subject_id},
        ).fetchone()
        if row is None:
            raise AppError(404, "NOT_FOUND", "Module not found")
        return as_uuid(module_id)
    return None


@router.get("/subjects/{subject_id}/co-sheet")
def co_sheet(
    subject_id: str,
    scope: str = "semester",
    module_id: str | None = None,
    section: str | None = None,
    conn=Depends(get_conn),
    user=Depends(require_faculty),
):
    sid = subject_for_faculty(conn, subject_id, user)["id"]
    sid = str(sid)
    mod = _check_scope(conn, sid, scope, module_id)
    return get_co_sheet_data(PostgresAnalyticsStore(conn), sid, scope=scope, module_id=mod, section=section)


@router.get("/subjects/{subject_id}/co-summary")
def co_summary(subject_id: str, section: str | None = None, conn=Depends(get_conn), user=Depends(require_faculty)):
    sid = str(subject_for_faculty(conn, subject_id, user)["id"])
    return get_class_summary_data(PostgresAnalyticsStore(conn), sid, section=section)


@router.get("/subjects/{subject_id}/weak-cos")
def weak_cos_route(subject_id: str, section: str | None = None, conn=Depends(get_conn), user=Depends(require_faculty)):
    sid = str(subject_for_faculty(conn, subject_id, user)["id"])
    return get_weak_cos_data(PostgresAnalyticsStore(conn), sid, section=section)


@router.get("/subjects/{subject_id}/cos/{co_id}/drilldown")
def co_drilldown_route(
    subject_id: str,
    co_id: str,
    module_id: str | None = None,
    section: str | None = None,
    conn=Depends(get_conn),
    user=Depends(require_faculty),
):
    sid = str(subject_for_faculty(conn, subject_id, user)["id"])
    cid = as_uuid(co_id, "Course outcome")
    owned = conn.execute(
        text("SELECT 1 FROM course_outcomes WHERE id = :c AND subject_id = :s"), {"c": cid, "s": sid}
    ).fetchone()
    if owned is None:
        raise AppError(404, "NOT_FOUND", "Course outcome not found")
    try:
        return get_co_drilldown_data(
            PostgresAnalyticsStore(conn), sid, cid,
            module_id=as_uuid(module_id, "Module") if module_id else None, section=section,
        )
    except NotFoundError as exc:
        raise AppError(404, "NOT_FOUND", str(exc)) from None


@router.get("/subjects/{subject_id}/co-sheet/export")
def co_sheet_export(
    subject_id: str,
    scope: str = "semester",
    module_id: str | None = None,
    section: str | None = None,
    conn=Depends(get_conn),
    user=Depends(require_faculty),
):
    subject = subject_for_faculty(conn, subject_id, user)
    sid = str(subject["id"])
    mod = _check_scope(conn, sid, scope, module_id)
    data = export_co_sheet_excel(PostgresAnalyticsStore(conn), sid, scope=scope, module_id=mod, section=section)
    safe_code = "".join(ch for ch in str(subject["code"]) if ch.isalnum() or ch in "-_") or "subject"
    return Response(
        content=data,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="co_sheet_{safe_code}.xlsx"'},
    )


def _progress(conn, user: dict, usn: str, subject_id: str) -> dict:
    try:
        return get_student_progress_data(
            PostgresAnalyticsStore(conn), current_user=user, usn=usn, subject_id=subject_id
        )
    except ForbiddenError as exc:
        raise AppError(403, "FORBIDDEN", str(exc)) from None
    except NotFoundError as exc:
        raise AppError(404, "NOT_FOUND", str(exc)) from None


# NOTE: /students/me/progress must stay above /students/{usn}/progress.
@router.get("/students/me/progress")
def my_progress(subject_id: str, conn=Depends(get_conn), user=Depends(get_current_user)):
    if user["role"] != "student":
        raise AppError(403, "FORBIDDEN", "Student access required")
    sid = str(subject_for_student(conn, subject_id, user)["id"])
    return _progress(conn, user, user["usn"], sid)


@router.get("/students/{usn}/progress")
def student_progress(usn: str, subject_id: str, conn=Depends(get_conn), user=Depends(get_current_user)):
    if user["role"] == "student":
        # Own USN only, checked before anything is read.
        if (user.get("usn") or "").strip().upper() != usn.strip().upper():
            raise AppError(403, "FORBIDDEN", "Students can only view their own progress")
        sid = str(subject_for_student(conn, subject_id, user)["id"])
    else:
        sid = str(subject_for_faculty(conn, subject_id, user)["id"])
    return _progress(conn, user, usn, sid)
