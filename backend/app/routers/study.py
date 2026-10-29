"""Study features endpoints.

Section 9 of docs/api-contract.md:
- POST /qa
- GET /retrieve?subject_id=&q=
- POST /students/me/study-plan
- GET /students/me/study-plan
- POST /modules/{id}/study-material
- GET /modules/{id}/flashcards
- GET /modules/{id}/notes
"""

from __future__ import annotations

from typing import Any, Sequence

from app.services.qa import ChunkRetrievalStore, answer_from_course_material, retrieve_chunks
from app.services.quizzes import ForbiddenError, NotFoundError
from app.services.study_material import (
    StudyMaterialStore,
    generate_module_study_material,
    get_module_flashcards,
    get_module_notes,
)
from app.services.study_plan import StudyPlanStore, build_study_plan, get_latest_study_plan

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, status
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


def format_error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


class StudyRouterHandler:
    def __init__(
        self,
        retrieval_store: ChunkRetrievalStore | None = None,
        material_store: StudyMaterialStore | None = None,
        plan_store: StudyPlanStore | None = None,
        chunk_provider: Any = None,
        score_provider: Any = None,
        co_provider: Any = None,
    ) -> None:
        self.retrieval_store = retrieval_store
        self.material_store = material_store
        self.plan_store = plan_store
        self.chunk_provider = chunk_provider
        self.score_provider = score_provider
        self.co_provider = co_provider

    def answer_question(
        self,
        current_user: dict[str, Any],
        subject_id: str,
        question: str,
    ) -> tuple[int, dict[str, Any]]:
        if not self.retrieval_store:
            return 500, format_error("INTERNAL_ERROR", "Retrieval store not configured.")

        res = answer_from_course_material(
            self.retrieval_store,
            subject_id=subject_id,
            question=question,
        )
        return 200, res.to_dict()

    def retrieve(
        self,
        current_user: dict[str, Any],
        subject_id: str,
        q: str,
    ) -> tuple[int, list[dict[str, Any]]]:
        if not self.retrieval_store:
            return 500, [format_error("INTERNAL_ERROR", "Retrieval store not configured.")]

        chunks = retrieve_chunks(self.retrieval_store, subject_id=subject_id, query=q)
        return 200, [c.to_dict() for c in chunks]

    def create_study_plan(
        self,
        current_user: dict[str, Any],
        subject_id: str,
    ) -> tuple[int, dict[str, Any]]:
        if current_user.get("role") != "student":
            return 403, format_error("FORBIDDEN", "Only students can generate personal study plans.")

        student_id = current_user.get("student_id")
        usn = current_user.get("usn")
        if not student_id or not self.plan_store:
            return 400, format_error("BAD_REQUEST", "Missing student identification or plan store.")

        scores = self.score_provider(student_id, subject_id) if self.score_provider else {}
        cos = self.co_provider(subject_id) if self.co_provider else {}
        chunks = self.chunk_provider(subject_id) if self.chunk_provider else []
        cards = []
        if self.material_store:
            # Gather cards from modules
            cards = []

        plan = build_study_plan(
            self.plan_store,
            student_id=student_id,
            subject_id=subject_id,
            student_co_percentages=scores,
            co_configs=cos,
            slide_chunks=chunks,
            flashcards=cards,
        )
        return 201, plan.to_dict()

    def get_study_plan(
        self,
        current_user: dict[str, Any],
        subject_id: str,
    ) -> tuple[int, dict[str, Any]]:
        if current_user.get("role") != "student":
            return 403, format_error("FORBIDDEN", "Only students can view their personal study plan.")

        student_id = current_user.get("student_id")
        if not student_id or not self.plan_store:
            return 404, format_error("NOT_FOUND", "No study plan available.")

        plan = get_latest_study_plan(self.plan_store, student_id, subject_id)
        if not plan:
            return 404, format_error("NOT_FOUND", "No study plan found for this subject.")
        return 200, plan

    def generate_material(
        self,
        current_user: dict[str, Any],
        module_id: str,
        module_title: str = "Course Module",
    ) -> tuple[int, dict[str, Any]]:
        if current_user.get("role") != "faculty":
            return 403, format_error("FORBIDDEN", "Only faculty can generate module study materials.")

        if not self.material_store:
            return 500, format_error("INTERNAL_ERROR", "Material store not configured.")

        chunks = self.chunk_provider(module_id) if self.chunk_provider else []
        cards, notes = generate_module_study_material(
            self.material_store,
            module_id=module_id,
            module_title=module_title,
            chunks=chunks,
        )
        return 200, {
            "flashcards": [c.to_dict() for c in cards],
            "notes": [n.to_dict() for n in notes],
        }

    def get_flashcards(
        self,
        current_user: dict[str, Any],
        module_id: str,
    ) -> tuple[int, list[dict[str, Any]]]:
        if not self.material_store:
            return 500, [format_error("INTERNAL_ERROR", "Material store not configured.")]

        cards = get_module_flashcards(self.material_store, module_id)
        return 200, cards

    def get_notes(
        self,
        current_user: dict[str, Any],
        module_id: str,
    ) -> tuple[int, list[dict[str, Any]]]:
        if not self.material_store:
            return 500, [format_error("INTERNAL_ERROR", "Material store not configured.")]

        notes = get_module_notes(self.material_store, module_id)
        return 200, notes


# ---------------------------------------------------------------------------
# Live routes (Postgres)
# ---------------------------------------------------------------------------

import logging

from pydantic import BaseModel, Field

from ..db import get_conn
from ..deps import get_current_user, require_faculty, require_student
from ..errors import AppError
from ..pg.analytics import PostgresAnalyticsStore
from ..pg.chunks import (
    PostgresChunkRetrievalStore,
    module_chunks_with_co,
    slide_chunks_for_subject,
    subject_cos,
)
from ..pg.common import module_for_user, subject_for_faculty, subject_for_student, subject_for_user
from ..pg.study import PostgresStudyMaterialStore, PostgresStudyPlanStore, subject_flashcards_with_co
from ..services.ai_glue import (
    UsageRecorder,
    get_client,
    make_material_generator,
    make_plan_generator,
    make_qa_client,
)
from ..services.co_analytics import get_student_progress_data

log = logging.getLogger(__name__)

router = APIRouter(tags=["study"])


class QARequest(BaseModel):
    subject_id: str
    question: str = Field(min_length=3, max_length=500)


class StudyPlanRequest(BaseModel):
    subject_id: str


def _close(client) -> None:
    if client is not None:
        client.close()


@router.post("/qa")
def qa(body: QARequest, conn=Depends(get_conn), user=Depends(get_current_user)):
    sid = str(subject_for_user(conn, body.subject_id, user)["id"])
    client = get_client()
    try:
        result = answer_from_course_material(
            PostgresChunkRetrievalStore(conn),
            sid,
            body.question.strip(),
            ai_client=make_qa_client(client, UsageRecorder(conn, user)),
        )
    finally:
        _close(client)
    return result.to_dict()


@router.get("/retrieve")
def retrieve(subject_id: str, q: str, conn=Depends(get_conn), user=Depends(get_current_user)):
    sid = str(subject_for_user(conn, subject_id, user)["id"])
    if not q.strip():
        raise AppError(422, "VALIDATION_ERROR", "q must not be empty")
    chunks = retrieve_chunks(PostgresChunkRetrievalStore(conn), sid, q.strip())
    return [c.to_dict() for c in chunks]


@router.post("/students/me/study-plan", status_code=201)
def create_my_study_plan(body: StudyPlanRequest, conn=Depends(get_conn), user=Depends(require_student)):
    sid = str(subject_for_student(conn, body.subject_id, user)["id"])
    progress = get_student_progress_data(
        PostgresAnalyticsStore(conn), current_user=user, usn=user["usn"], subject_id=sid
    )
    scores = {row["co_number"]: row["percentage"] for row in progress["co_scores"]}
    cos = {
        c["number"]: {"id": c["id"], "threshold_pct": c["threshold_pct"], "description": c["description"]}
        for c in subject_cos(conn, sid)
    }
    client = get_client()
    try:
        plan = build_study_plan(
            PostgresStudyPlanStore(conn),
            student_id=user["student_id"],
            subject_id=sid,
            student_co_percentages=scores,
            co_configs=cos,
            slide_chunks=slide_chunks_for_subject(conn, sid),
            flashcards=subject_flashcards_with_co(conn, sid),
            ai_generator=make_plan_generator(client, UsageRecorder(conn, user), cos),
        )
    finally:
        _close(client)
    return plan.to_dict()


@router.get("/students/me/study-plan")
def get_my_study_plan(subject_id: str, conn=Depends(get_conn), user=Depends(require_student)):
    sid = str(subject_for_student(conn, subject_id, user)["id"])
    plan = get_latest_study_plan(PostgresStudyPlanStore(conn), user["student_id"], sid)
    if plan is None:
        raise AppError(404, "NOT_FOUND", "No study plan yet for this subject")
    return plan


@router.post("/modules/{module_id}/study-material")
def generate_study_material(
    module_id: str, regenerate: bool = False, conn=Depends(get_conn), user=Depends(require_faculty)
):
    module = module_for_user(conn, module_id, user)
    subject_for_faculty(conn, str(module["subject_id"]), user)
    mid = str(module["id"])
    chunks = module_chunks_with_co(conn, mid)
    if not chunks:
        raise AppError(409, "CONFLICT", "Upload and process the module's slides first.")

    store = PostgresStudyMaterialStore(conn)
    if regenerate:
        store.delete_for_module(mid)

    client = get_client()
    try:
        generator = make_material_generator(client, UsageRecorder(conn, user), chunks)
        try:
            cards, notes = generate_module_study_material(store, mid, module["title"], chunks, generator=generator)
        except Exception:
            if generator is None:
                raise
            log.warning("AI flashcard generation failed; using slide text", exc_info=True)
            cards, notes = generate_module_study_material(store, mid, module["title"], chunks, generator=None)
    finally:
        _close(client)
    return {"flashcards": [c.to_dict() for c in cards], "notes": [n.to_dict() for n in notes]}


@router.get("/modules/{module_id}/flashcards")
def list_flashcards(module_id: str, conn=Depends(get_conn), user=Depends(get_current_user)):
    module = module_for_user(conn, module_id, user)
    return get_module_flashcards(PostgresStudyMaterialStore(conn), str(module["id"]))


@router.get("/modules/{module_id}/notes")
def list_notes(module_id: str, conn=Depends(get_conn), user=Depends(get_current_user)):
    module = module_for_user(conn, module_id, user)
    return get_module_notes(PostgresStudyMaterialStore(conn), str(module["id"]))
