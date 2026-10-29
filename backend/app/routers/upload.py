"""Upload and coverage endpoints.

Section 6 of docs/api-contract.md:
- POST /modules/{module_id}/upload
- GET /modules/{module_id}/status
- GET /subjects/{subject_id}/coverage
"""

from __future__ import annotations

import io
from typing import Any, BinaryIO, Sequence

from sqlalchemy import text

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


# ---------------------------------------------------------------------------
# Live routes (Postgres). The handler class above stays as the unit-tested logic.
# ---------------------------------------------------------------------------

import logging

from fastapi import BackgroundTasks

from ..db import get_conn, get_engine
from ..deps import require_faculty
from ..errors import AppError
from ..pg.chunks import PostgresChunkStore, chunk_co_links, module_status, subject_cos
from ..pg.common import module_for_user, subject_for_faculty
from ..pg.usage import PostgresUsageStore  # noqa: F401  (kept for symmetry with other routers)
from ..services.ai_glue import UsageRecorder, get_client, make_tagger

log = logging.getLogger(__name__)

router = APIRouter(tags=["upload"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _co_infos(conn, subject_id: str) -> list[COInfo]:
    return [COInfo(number=c["number"], description=c["description"] or "") for c in subject_cos(conn, subject_id)]


def run_upload_pipeline(module_id: str, subject_id: str, data: bytes, user: dict) -> None:
    """Parse, save and tag one deck on its own connection (runs after the response is sent).

    A plain function with no request objects, so it can move to a Nebius Serverless Job.
    """
    engine = get_engine()
    with engine.connect() as conn:
        store = PostgresChunkStore(conn, subject_id, commit_status=True)
        try:
            recorder = UsageRecorder(conn, user)
            client = get_client()
            try:
                process_module_upload(
                    module_id=module_id,
                    source=io.BytesIO(data),
                    cos=_co_infos(conn, subject_id),
                    tagger=make_tagger(client, recorder),
                    store=store,
                )
            finally:
                if client is not None:
                    client.close()
            conn.commit()
        except Exception as exc:  # the pipeline already marked the module failed; record why
            log.exception("upload pipeline crashed for module %s", module_id)
            conn.rollback()
            store.set_module_status(module_id, "failed", f"Upload failed: {exc}"[:500])


@router.post("/modules/{module_id}/upload", status_code=202)
async def upload_module(
    module_id: str,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    conn=Depends(get_conn),
    user=Depends(require_faculty),
):
    module = module_for_user(conn, module_id, user)
    subject_for_faculty(conn, str(module["subject_id"]), user)

    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".pptx"):
        raise AppError(400, "BAD_REQUEST", "Only .pptx files are supported.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise AppError(400, "BAD_REQUEST", "File is larger than 25 MB.")
    if not data.startswith(b"PK"):
        raise AppError(400, "BAD_REQUEST", "That file is not a valid .pptx presentation.")
    if module["processing_status"] == "processing":
        raise AppError(409, "CONFLICT", "This module is already being processed.")

    conn.execute(
        text("UPDATE modules SET ppt_file_path = :f WHERE id = :id"),
        {"f": filename[:200], "id": str(module["id"])},
    )
    PostgresChunkStore(conn, str(module["subject_id"]), commit_status=True).set_module_status(
        str(module["id"]), "processing"
    )
    background.add_task(run_upload_pipeline, str(module["id"]), str(module["subject_id"]), data, user)
    return {"module_id": str(module["id"]), "processing_status": "processing"}


@router.get("/modules/{module_id}/status")
def get_module_status(module_id: str, conn=Depends(get_conn), user=Depends(require_faculty)):
    module = module_for_user(conn, module_id, user)
    subject_for_faculty(conn, str(module["subject_id"]), user)
    info = module_status(conn, str(module["id"]))
    if info is None:
        raise AppError(404, "NOT_FOUND", "Module not found")
    return info


@router.get("/subjects/{subject_id}/coverage")
def get_subject_coverage(subject_id: str, conn=Depends(get_conn), user=Depends(require_faculty)):
    subject = subject_for_faculty(conn, subject_id, user)
    sid = str(subject["id"])
    cos = subject_cos(conn, sid)
    results = coverage([c["number"] for c in cos], chunk_co_links(conn, sid))
    id_by_number = {c["number"]: c["id"] for c in cos}
    return [
        {
            "co_id": id_by_number[r.co],
            "co_number": r.co,
            "chunk_count": r.chunk_count,
            "warning": r.warning,
            "message": r.message,
        }
        for r in results
    ]
