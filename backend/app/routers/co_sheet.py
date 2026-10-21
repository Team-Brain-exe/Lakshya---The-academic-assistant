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


router = APIRouter() if HAS_FASTAPI else None

