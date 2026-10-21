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


router = APIRouter() if HAS_FASTAPI else None

