"""CO Sheet and analytics services.

Adapts stored quiz scores and student data into CO sheets, class summaries,
weak-CO flags, drill-down breakdowns, Excel exports, and student progress reports.
Matching arya.md tasks 6 & 7 and docs/api-contract.md section 8.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from app.engine.co_math import (
    AttemptScore,
    COConfig,
    CODrilldown,
    COSheet,
    COSummary,
    CountedScore,
    StudentInfo,
    WeakCO,
    build_co_sheet,
    class_summary,
    co_drilldown,
    select_counted,
    weak_cos,
)
from app.engine.settings import load_grading_settings
from app.export.sheet_xlsx import build_sheet_workbook
from app.services.quizzes import ForbiddenError, NotFoundError


class AnalyticsStore(Protocol):
    """Protocol for reading academic and score data for analytics."""

    def get_subject_cos(self, subject_id: str) -> list[COConfig]: ...

    def get_subject_roster(self, subject_id: str) -> list[StudentInfo]: ...

    def get_subject_attempts(self, subject_id: str) -> list[AttemptScore]: ...

    def get_co_by_id(self, co_id: str) -> COConfig | None: ...

    def get_student_by_usn(self, usn: str) -> StudentInfo | None: ...

    def get_student_progress(self, student_id: str, subject_id: str) -> dict[str, Any]: ...


class InMemoryAnalyticsStore:
    """In-memory store for unit tests and local execution."""

    def __init__(
        self,
        cos: list[COConfig] | None = None,
        roster: list[StudentInfo] | None = None,
        attempts: list[AttemptScore] | None = None,
        co_id_map: dict[str, COConfig] | None = None,
        progress_map: dict[tuple[str, str], dict[str, Any]] | None = None,
    ) -> None:
        self.cos = cos or []
        self.roster = roster or []
        self.attempts = attempts or []
        self.co_id_map = co_id_map or {}
        self.progress_map = progress_map or {}

    def get_subject_cos(self, subject_id: str) -> list[COConfig]:
        return list(self.cos)

    def get_subject_roster(self, subject_id: str) -> list[StudentInfo]:
        return list(self.roster)

    def get_subject_attempts(self, subject_id: str) -> list[AttemptScore]:
        return list(self.attempts)

    def get_co_by_id(self, co_id: str) -> COConfig | None:
        return self.co_id_map.get(co_id)

    def get_student_by_usn(self, usn: str) -> StudentInfo | None:
        for s in self.roster:
            if s.usn == usn:
                return s
        return None

    def get_student_progress(self, student_id: str, subject_id: str) -> dict[str, Any]:
        return self.progress_map.get((student_id, subject_id), {"co_scores": [], "attempts": []})


def _build_counted(store: AnalyticsStore, subject_id: str) -> list[CountedScore]:
    attempts = store.get_subject_attempts(subject_id)
    rule = load_grading_settings().attempt_rule
    return select_counted(attempts, rule)


def get_co_sheet_data(
    store: AnalyticsStore,
    subject_id: str,
    *,
    scope: str = "semester",
    module_id: str | None = None,
    section: str | None = None,
) -> dict[str, Any]:
    """Build the CO sheet matrix for GET /subjects/{id}/co-sheet."""
    cos = store.get_subject_cos(subject_id)
    roster = store.get_subject_roster(subject_id)
    counted = _build_counted(store, subject_id)

    mod_filter = module_id if scope == "module" else None
    sheet = build_co_sheet(counted, roster, cos, module_id=mod_filter, section=section)

    rows_data = []
    for r in sheet.rows:
        rows_data.append({
            "usn": r.usn,
            "name": r.name,
            "section": r.section,
            "co_scores": {f"CO{k}": v for k, v in r.co_scores.items()},
            "total": r.total_pct,
            "total_obtained": r.total_obtained,
            "total_max": r.total_max,
            "total_pct": r.total_pct,
        })

    return {
        "columns": [f"CO{c}" for c in sheet.co_numbers],
        "rows": rows_data,
        "averages": {f"CO{k}": v for k, v in sheet.averages.items()},
    }


def get_class_summary_data(
    store: AnalyticsStore,
    subject_id: str,
    *,
    section: str | None = None,
) -> list[dict[str, Any]]:
    """Build class summary per CO for GET /subjects/{id}/co-summary."""
    cos = store.get_subject_cos(subject_id)
    roster = store.get_subject_roster(subject_id)
    counted = _build_counted(store, subject_id)

    sheet = build_co_sheet(counted, roster, cos, section=section)
    summaries = class_summary(sheet, cos)

    return [
        {
            "co_number": s.co,
            "threshold_pct": s.threshold_pct,
            "target_pct": s.target_pct,
            "enrolled": s.enrolled,
            "attempted": s.attempted,
            "average": s.average,
            "above": s.above,
            "below": s.below,
            "attainment_pct": s.attainment_pct,
            "met": s.met,
            "target_met": s.met,
            "gap": s.gap,
        }
        for s in summaries
    ]


def get_weak_cos_data(
    store: AnalyticsStore,
    subject_id: str,
    *,
    section: str | None = None,
) -> list[dict[str, Any]]:
    """Get COs below target for GET /subjects/{id}/weak-cos and find_weak_COs tool."""
    cos = store.get_subject_cos(subject_id)
    roster = store.get_subject_roster(subject_id)
    counted = _build_counted(store, subject_id)

    sheet = build_co_sheet(counted, roster, cos, section=section)
    summaries = class_summary(sheet, cos)
    weak_list = weak_cos(summaries)

    return [
        {
            "co_number": w.co,
            "attainment_pct": w.attainment_pct,
            "target_pct": w.target_pct,
            "gap": w.gap,
        }
        for w in weak_list
    ]


def get_co_drilldown_data(
    store: AnalyticsStore,
    subject_id: str,
    co_id: str,
    *,
    module_id: str | None = None,
    section: str | None = None,
) -> dict[str, Any]:
    """Drilldown breakdown behind one CO for GET /subjects/{id}/cos/{co_id}/drilldown."""
    cfg = store.get_co_by_id(co_id)
    if not cfg:
        raise NotFoundError(f"Course Outcome {co_id} not found.")

    roster = store.get_subject_roster(subject_id)
    counted = _build_counted(store, subject_id)

    dd = co_drilldown(counted, roster, cfg, module_id=module_id, section=section)

    return {
        "co_number": dd.co,
        "threshold_pct": dd.threshold_pct,
        "modules": [
            {
                "module_id": m.module_id,
                "obtained": m.obtained,
                "maximum": m.maximum,
                "percentage": m.percentage,
                "students": m.students,
            }
            for m in dd.modules
        ],
        "questions": [
            {
                "question_id": q.question_id,
                "module_id": q.module_id,
                "samples": q.samples,
                "correct": q.correct,
                "correct_pct": q.correct_pct,
            }
            for q in dd.questions
        ],
        "students": [
            {
                "usn": s.usn,
                "name": s.name,
                "section": s.section,
                "obtained": s.obtained,
                "maximum": s.maximum,
                "percentage": s.percentage,
                "attained": s.attained,
            }
            for s in dd.students
        ],
        "not_attempted": dd.not_attempted,
    }


def export_co_sheet_excel(
    store: AnalyticsStore,
    subject_id: str,
    *,
    scope: str = "semester",
    module_id: str | None = None,
    section: str | None = None,
) -> bytes:
    """Generate Excel bytes for GET /subjects/{id}/co-sheet/export."""
    cos = store.get_subject_cos(subject_id)
    roster = store.get_subject_roster(subject_id)
    counted = _build_counted(store, subject_id)

    mod_filter = module_id if scope == "module" else None
    sheet = build_co_sheet(counted, roster, cos, module_id=mod_filter, section=section)
    summaries = class_summary(sheet, cos)

    thresholds = {c.number: c.threshold_pct for c in cos}
    return build_sheet_workbook(sheet, thresholds=thresholds, summary=summaries)


def get_student_progress_data(
    store: AnalyticsStore,
    current_user: dict[str, Any],
    usn: str,
    subject_id: str,
) -> dict[str, Any]:
    """Retrieve student's CO progress.
    
    Rule: Student can ONLY view their own USN. Requesting another USN returns 403 Forbidden.
    Faculty can view any student's progress in their subject.
    """
    normalized_usn = usn.strip().upper()
    role = current_user.get("role")
    caller_usn = (current_user.get("usn") or "").strip().upper()

    if role == "student" and caller_usn != normalized_usn:
        raise ForbiddenError(f"Students are not permitted to view data of USN {normalized_usn}.")

    student = store.get_student_by_usn(normalized_usn)
    if not student:
        raise NotFoundError(f"Student with USN {normalized_usn} not found.")

    cos = store.get_subject_cos(subject_id)
    threshold_by_co = {c.number: c.threshold_pct for c in cos}

    counted = _build_counted(store, subject_id)
    # Filter counted scores for this student
    student_counted = [c for c in counted if c.usn == normalized_usn]

    # Aggregate CO marks for this student
    obtained_by_co: dict[int, float] = {}
    max_by_co: dict[int, float] = {}
    for c in student_counted:
        for co_num, m in c.per_co.items():
            obtained_by_co[co_num] = obtained_by_co.get(co_num, 0.0) + m.obtained
            max_by_co[co_num] = max_by_co.get(co_num, 0.0) + m.maximum

    co_scores_list = []
    for c in cos:
        co_num = c.number
        ob = obtained_by_co.get(co_num)
        mx = max_by_co.get(co_num)
        pct = (ob * 100 / mx) if mx and mx > 0 else None
        co_scores_list.append({
            "co_number": co_num,
            "marks_obtained": ob,
            "max_marks": mx,
            "percentage": pct,
            "threshold_pct": c.threshold_pct,
            "attained": pct is not None and pct >= c.threshold_pct,
        })

    # List attempts for this student
    attempts_list = [
        {
            "quiz_id": c.quiz_id,
            "module_id": c.module_id,
            "co_scores": {f"CO{k}": m.percentage for k, m in c.per_co.items()},
        }
        for c in student_counted
    ]

    return {
        "usn": normalized_usn,
        "name": student.name,
        "section": student.section,
        "subject_id": subject_id,
        "co_scores": co_scores_list,
        "attempts": attempts_list,
    }

