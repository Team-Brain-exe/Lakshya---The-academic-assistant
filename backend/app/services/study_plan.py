"""Student personalized study plan generation service.

Generates targeted study plans based on a student's weak Course Outcomes,
linking to relevant slides and flashcards, matching arya.md task 9.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class StudyStep:
    co_number: int
    recommendation: str
    slides: list[dict[str, Any]]
    flashcards: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "co_number": self.co_number,
            "recommendation": self.recommendation,
            "slides": self.slides,
            "flashcards": self.flashcards,
        }


@dataclass(frozen=True)
class StudentStudyPlan:
    id: str
    student_id: str
    subject_id: str
    weak_co_ids: list[str]
    plan: dict[str, Any]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "student_id": self.student_id,
            "subject_id": self.subject_id,
            "weak_co_ids": self.weak_co_ids,
            "plan": self.plan,
            "generated_at": self.generated_at.isoformat(),
        }


class StudyPlanStore(Protocol):
    """Protocol for study plan persistence."""

    def save_plan(self, plan: StudentStudyPlan) -> None: ...

    def get_latest_plan(self, student_id: str, subject_id: str) -> StudentStudyPlan | None: ...


class InMemoryStudyPlanStore:
    def __init__(self) -> None:
        # (student_id, subject_id) -> list of plans (latest last)
        self._plans: dict[tuple[str, str], list[StudentStudyPlan]] = {}

    def save_plan(self, plan: StudentStudyPlan) -> None:
        key = (plan.student_id, plan.subject_id)
        self._plans.setdefault(key, []).append(plan)

    def get_latest_plan(self, student_id: str, subject_id: str) -> StudentStudyPlan | None:
        plans = self._plans.get((student_id, subject_id), [])
        return plans[-1] if plans else None


# AI Plan Generator: (weak_cos, matching_slides, matching_cards) -> list[StudyStep]
PlanAIGenerator = Callable[[list[int], list[dict[str, Any]], list[dict[str, Any]]], list[dict[str, Any]]]


def build_study_plan(
    store: StudyPlanStore,
    student_id: str,
    subject_id: str,
    student_co_percentages: Mapping[int, float | None],
    co_configs: Mapping[int, dict[str, Any]],  # co_number -> {id, threshold_pct, description}
    slide_chunks: Sequence[dict[str, Any]],     # [{slide_number, module_id, co_number, text}]
    flashcards: Sequence[dict[str, Any]],       # [{id, co_number, front, back}]
    *,
    ai_generator: PlanAIGenerator | None = None,
    plan_id: str | None = None,
) -> StudentStudyPlan:
    """Build and store a personalized study plan for a student.
    
    Identifies weak COs (where student's score is below threshold or unattempted),
    finds relevant slides and flashcards, and formats progressive study steps.
    """
    weak_co_numbers: list[int] = []
    weak_co_ids: list[str] = []

    for co_num, cfg in sorted(co_configs.items()):
        threshold = cfg.get("threshold_pct", 60.0)
        pct = student_co_percentages.get(co_num)
        # Weak if no score or below threshold
        if pct is None or pct < threshold:
            weak_co_numbers.append(co_num)
            if "id" in cfg:
                weak_co_ids.append(cfg["id"])

    # If student attained everything, pick lowest performing CO or return maintenance plan
    if not weak_co_numbers and student_co_percentages:
        # Find lowest scoring CO
        sorted_cos = sorted(
            [(num, pct) for num, pct in student_co_percentages.items() if pct is not None],
            key=lambda x: x[1],
        )
        if sorted_cos:
            lowest_co = sorted_cos[0][0]
            weak_co_numbers.append(lowest_co)
            if "id" in co_configs.get(lowest_co, {}):
                weak_co_ids.append(co_configs[lowest_co]["id"])

    steps: list[dict[str, Any]] = []

    if ai_generator is not None:
        steps = ai_generator(weak_co_numbers, list(slide_chunks), list(flashcards))
    else:
        # Grounded step builder
        for co_num in weak_co_numbers:
            cfg = co_configs.get(co_num, {})
            desc = cfg.get("description", f"Course Outcome {co_num}")

            # Linked slides for this CO
            rel_slides = [
                {
                    "module_id": ch.get("module_id"),
                    "slide_number": ch.get("slide_number"),
                    "summary": ch.get("text", "")[:120] + "...",
                }
                for ch in slide_chunks
                if ch.get("co_number") == co_num
            ]

            # Linked flashcards for this CO
            rel_cards = [
                {
                    "id": fc.get("id"),
                    "front": fc.get("front"),
                    "back": fc.get("back"),
                }
                for fc in flashcards
                if fc.get("co_number") == co_num
            ]

            steps.append({
                "co_number": co_num,
                "goal": f"Master CO{co_num}: {desc}",
                "recommendation": (
                    f"Focus on the {len(rel_slides)} key slides and practice with {len(rel_cards)} flashcards "
                    f"to bring your attainment above the {cfg.get('threshold_pct', 60.0)}% threshold."
                ),
                "slides": rel_slides[:5],
                "flashcards": rel_cards[:5],
            })

    plan_payload = {
        "title": "Personalized Remedial Study Plan",
        "weak_cos": weak_co_numbers,
        "steps": steps,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    plan = StudentStudyPlan(
        id=plan_id or str(uuid.uuid4()),
        student_id=student_id,
        subject_id=subject_id,
        weak_co_ids=weak_co_ids,
        plan=plan_payload,
    )
    store.save_plan(plan)
    return plan


def get_latest_study_plan(
    store: StudyPlanStore, student_id: str, subject_id: str
) -> dict[str, Any] | None:
    plan = store.get_latest_plan(student_id, subject_id)
    return plan.to_dict() if plan else None

