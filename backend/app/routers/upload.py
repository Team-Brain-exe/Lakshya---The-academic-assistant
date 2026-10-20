"""Upload and coverage endpoints.

Section 6 of docs/api-contract.md:
- POST /modules/{module_id}/upload
- GET /modules/{module_id}/status
- GET /subjects/{subject_id}/coverage
"""

from __future__ import annotations

import io
from typing import Any, BinaryIO, Sequence

from app.pipeline.coverage import coverage
from app.pipeline.upload import COInfo, UploadReport, process_module_upload
from app.services.quizzes import ForbiddenError, NotFoundError

try:
    from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
    from fastapi.responses import JSONResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


def format_error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


class UploadRouterHandler:
    def __init__(self, store: Any = None, tagger: Any = None, cos_provider: Any = None) -> None:
        self.store = store
        self.tagger = tagger
        self.cos_provider = cos_provider
        self.statuses: dict[str, dict[str, Any]] = {}

    def upload_deck(
        self,
        current_user: dict[str, Any],
        module_id: str,
        file_bytes: bytes,
        filename: str = "slides.pptx",
    ) -> tuple[int, dict[str, Any]]:
        if current_user.get("role") != "faculty":
            return 403, format_error("FORBIDDEN", "Only faculty can upload course modules.")

        if not filename.endswith(".pptx"):
            return 400, format_error("BAD_REQUEST", "Only .pptx files are supported.")

        cos = []
        if self.cos_provider:
            cos = self.cos_provider(module_id)

        # Execute upload pipeline
        try:
            report = process_module_upload(
                module_id=module_id,
                source=io.BytesIO(file_bytes),
                cos=cos,
                tagger=self.tagger or (lambda chunks, cos: []),
                store=self.store,
            )
            self.statuses[module_id] = {
                "processing_status": report.status,
                "chunks_total": report.total_slides,
                "chunks_tagged": report.tagged,
                "chunks_untagged": report.untagged,
                "error": report.error,
            }
            return 202, {"module_id": module_id, "processing_status": report.status}
        except Exception as exc:
            self.statuses[module_id] = {
                "processing_status": "failed",
                "chunks_total": 0,
                "chunks_tagged": 0,
                "chunks_untagged": 0,
                "error": str(exc),
            }
            return 500, format_error("INTERNAL_ERROR", f"Pipeline error: {exc}")

    def get_status(
        self,
        current_user: dict[str, Any],
        module_id: str,
    ) -> tuple[int, dict[str, Any]]:
        if current_user.get("role") != "faculty":
            return 403, format_error("FORBIDDEN", "Only faculty can view upload status.")

        status_info = self.statuses.get(module_id)
        if not status_info:
            return 404, format_error("NOT_FOUND", f"Module {module_id} status not found.")

        return 200, status_info

    def get_coverage(
        self,
        current_user: dict[str, Any],
        subject_id: str,
        co_numbers: Sequence[int],
        links: Sequence[tuple[str, int]],
    ) -> tuple[int, list[dict[str, Any]]]:
        if current_user.get("role") != "faculty":
            return 403, [format_error("FORBIDDEN", "Only faculty can view CO coverage.")]

        cov_results = coverage(co_numbers, links)
        return 200, [
            {
                "co_id": f"co-{c.co}",
                "co_number": c.co,
                "chunk_count": c.chunk_count,
                "warning": c.warning,
            }
            for c in cov_results
        ]


router = APIRouter() if HAS_FASTAPI else None

