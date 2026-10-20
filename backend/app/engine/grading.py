"""Grading and per-CO marks.

Plain code. No LLM ever computes or changes a mark.

Rules (from the brief, section 6):
- Every question belongs to exactly one CO.
- A question the student left blank, or answered with an invalid option, earns 0
  but still counts toward the maximum, because it was shown to the student.
- A CO that has no questions in the attempt does not appear in the result. Its
  percentage is "no data" (None), never 0.
- Marks should be whole or half numbers so sums stay exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

# Floating point guard for threshold comparisons such as 59.99999999 vs 60.
_EPSILON = 1e-9


def percentage(obtained: float, maximum: float) -> float | None:
    """Return obtained / maximum as a percentage, or None when there is no maximum."""
    if maximum <= 0:
        return None
    return obtained * 100 / maximum


def meets_threshold(pct: float | None, threshold_pct: float) -> bool:
    """True when pct is present and at or above the threshold."""
    return pct is not None and pct >= threshold_pct - _EPSILON


def round2(value: float | None) -> float | None:
    """Round for display and export (2 decimal places). None stays None."""
    return None if value is None else round(value, 2)


@dataclass(frozen=True)
class QuestionKey:
    """What grading needs to know about a question."""

    id: str
    co: int
    correct_option: int
    marks: float = 1

    def __post_init__(self) -> None:
        if self.marks <= 0:
            raise ValueError(f"Question {self.id}: marks must be positive, got {self.marks}")
        if self.correct_option < 0:
            raise ValueError(f"Question {self.id}: correct_option must be 0 or more")


@dataclass(frozen=True)
class COMarks:
    """Marks obtained and maximum for one CO."""

    co: int
    obtained: float
    maximum: float

    @property
    def percentage(self) -> float | None:
        return percentage(self.obtained, self.maximum)


@dataclass(frozen=True)
class QuestionResult:
    question_id: str
    co: int
    chosen: int | None
    correct_option: int
    is_correct: bool
    marks_awarded: float
    marks_max: float


@dataclass(frozen=True)
class GradeResult:
    total_obtained: float
    total_max: float
    per_co: Mapping[int, COMarks]
    questions: tuple[QuestionResult, ...]

    @property
    def percentage(self) -> float | None:
        return percentage(self.total_obtained, self.total_max)


def _valid_choice(value: object) -> int | None:
    """An answer is usable only if it is a whole number 0 or more (bool is not a choice)."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def grade_attempt(
    questions: Sequence[QuestionKey],
    answers: Mapping[str, int | None],
) -> GradeResult:
    """Grade one attempt.

    questions: every question shown in the quiz.
    answers:   question id -> chosen option index. Missing or None means unanswered.
               Ids that are not in the quiz are ignored.
    """
    seen: set[str] = set()
    for q in questions:
        if q.id in seen:
            raise ValueError(f"Duplicate question id in quiz: {q.id}")
        seen.add(q.id)

    results: list[QuestionResult] = []
    obtained_by_co: dict[int, float] = {}
    max_by_co: dict[int, float] = {}

    for q in questions:
        chosen = _valid_choice(answers.get(q.id))
        correct = chosen is not None and chosen == q.correct_option
        awarded = q.marks if correct else 0
        results.append(
            QuestionResult(
                question_id=q.id,
                co=q.co,
                chosen=chosen,
                correct_option=q.correct_option,
                is_correct=correct,
                marks_awarded=awarded,
                marks_max=q.marks,
            )
        )
        obtained_by_co[q.co] = obtained_by_co.get(q.co, 0) + awarded
        max_by_co[q.co] = max_by_co.get(q.co, 0) + q.marks

    per_co = {
        co: COMarks(co=co, obtained=obtained_by_co[co], maximum=max_by_co[co])
        for co in sorted(max_by_co)
    }
    return GradeResult(
        total_obtained=sum(obtained_by_co.values()),
        total_max=sum(max_by_co.values()),
        per_co=per_co,
        questions=tuple(results),
    )
