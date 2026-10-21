"""CO scores, the CO sheet, class summary and weak-CO flag.

Plain code. Nothing here calls an LLM.

How the numbers are built (brief, section 6):
1. Each attempt is graded into per-CO marks (see grading.py).
2. The attempt rule (best, latest or average) picks which attempt counts for each
   student and quiz.
3. A student's CO score is  sum(obtained) / sum(maximum) * 100  over the counted
   quizzes in scope (one module, or the whole semester).
4. A CO with no questions in scope is "no data" (None). It is never 0, and it is
   left out of averages.
5. Class attainment for a CO is the share of students whose CO score is at or above
   the CO threshold. By default the denominator is every enrolled student, as in the
   brief; pass denominator="attempted" to use only students who have a score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Mapping, Sequence

from .grading import COMarks, GradeResult, QuestionResult, meets_threshold, percentage
from .settings import VALID_ATTEMPT_RULES

_EPSILON = 1e-9


# --------------------------------------------------------------------------- inputs


@dataclass(frozen=True)
class COConfig:
    """Per-CO settings. There are deliberately no defaults: faculty set the real values."""

    number: int
    threshold_pct: float  # a student's CO score at or above this counts as attained
    target_pct: float  # the share of the class that should reach the threshold


@dataclass(frozen=True)
class StudentInfo:
    usn: str
    name: str = ""
    section: str | None = None


@dataclass(frozen=True)
class AttemptScore:
    """One graded attempt of one quiz by one student."""

    usn: str
    quiz_id: str
    module_id: str
    attempt_number: int
    per_co: Mapping[int, COMarks]
    # Per-question results. Optional: only the drill-down needs them.
    questions: tuple[QuestionResult, ...] = ()

    @property
    def total_obtained(self) -> float:
        return sum(m.obtained for m in self.per_co.values())

    @classmethod
    def from_grade(
        cls, usn: str, quiz_id: str, module_id: str, attempt_number: int, grade: GradeResult
    ) -> "AttemptScore":
        return cls(
            usn, quiz_id, module_id, attempt_number, dict(grade.per_co), tuple(grade.questions)
        )


@dataclass(frozen=True)
class CountedScore:
    """The score that counts for one student on one quiz, after the attempt rule."""

    usn: str
    quiz_id: str
    module_id: str
    per_co: Mapping[int, COMarks]
    # Question results behind the counted score. Under "average" this holds the
    # results of every attempt, so each question has one sample per attempt.
    questions: tuple[QuestionResult, ...] = ()


# ----------------------------------------------------------------------- attempt rule


def _average_attempts(attempts: Sequence[AttemptScore]) -> dict[int, COMarks]:
    """Mean of obtained and of maximum, per CO, over the attempts that include that CO."""
    cos = sorted({co for a in attempts for co in a.per_co})
    out: dict[int, COMarks] = {}
    for co in cos:
        marks = [a.per_co[co] for a in attempts if co in a.per_co]
        out[co] = COMarks(
            co=co,
            obtained=sum(m.obtained for m in marks) / len(marks),
            maximum=sum(m.maximum for m in marks) / len(marks),
        )
    return out


def select_counted(attempts: Iterable[AttemptScore], rule: str) -> list[CountedScore]:
    """Pick the counted score for each (student, quiz).

    best     attempt with the highest total marks; on a tie, the later attempt
    latest   attempt with the highest attempt number
    average  mean of all attempts, per CO
    """
    if rule not in VALID_ATTEMPT_RULES:
        raise ValueError(f"Unknown attempt rule {rule!r}; use one of {VALID_ATTEMPT_RULES}")

    groups: dict[tuple[str, str], list[AttemptScore]] = {}
    seen: set[tuple[str, str, int]] = set()
    for a in attempts:
        key3 = (a.usn, a.quiz_id, a.attempt_number)
        if key3 in seen:
            raise ValueError(
                f"Duplicate attempt {a.attempt_number} for {a.usn} on quiz {a.quiz_id}"
            )
        seen.add(key3)
        groups.setdefault((a.usn, a.quiz_id), []).append(a)

    counted: list[CountedScore] = []
    for (usn, quiz_id), group in sorted(groups.items()):
        group.sort(key=lambda a: a.attempt_number)
        if rule == "latest":
            chosen = group[-1]
            per_co: Mapping[int, COMarks] = chosen.per_co
            questions = chosen.questions
        elif rule == "best":
            chosen = max(group, key=lambda a: (a.total_obtained, a.attempt_number))
            per_co = chosen.per_co
            questions = chosen.questions
        else:
            per_co = _average_attempts(group)
            questions = tuple(q for a in group for q in a.questions)
        counted.append(CountedScore(usn, quiz_id, group[-1].module_id, per_co, questions))
    return counted


# ----------------------------------------------------------------------- student x CO


def aggregate_student_scores(
    counted: Iterable[CountedScore], module_id: str | None = None
) -> dict[str, dict[int, COMarks]]:
    """Sum counted marks per student and CO. module_id=None means the whole semester."""
    totals: dict[str, dict[int, list[float]]] = {}
    for c in counted:
        if module_id is not None and c.module_id != module_id:
            continue
        per_student = totals.setdefault(c.usn, {})
        for co, m in c.per_co.items():
            cell = per_student.setdefault(co, [0.0, 0.0])
            cell[0] += m.obtained
            cell[1] += m.maximum
    return {
        usn: {co: COMarks(co, ob, mx) for co, (ob, mx) in sorted(cos.items())}
        for usn, cos in totals.items()
    }


# ---------------------------------------------------------------------------- sheet


@dataclass(frozen=True)
class SheetRow:
    usn: str
    name: str
    section: str | None
    co_scores: Mapping[int, float | None]  # percentage, None = no data for that CO
    total_obtained: float
    total_max: float
    total_pct: float | None


@dataclass(frozen=True)
class COSheet:
    co_numbers: tuple[int, ...]
    rows: tuple[SheetRow, ...]
    averages: Mapping[int, float | None]  # mean of the students who have data


def build_co_sheet(
    counted: Iterable[CountedScore],
    roster: Iterable[StudentInfo],
    cos: Sequence[COConfig],
    module_id: str | None = None,
    section: str | None = None,
) -> COSheet:
    """Student x CO x total, sorted by USN.

    Every rostered student gets a row, even with no attempts (all None). Scores for
    students who are not on the roster, and for COs that are not configured, are left out.
    """
    co_numbers = tuple(sorted(c.number for c in cos))
    scores = aggregate_student_scores(counted, module_id)

    rows: list[SheetRow] = []
    for s in sorted(roster, key=lambda s: s.usn):
        if section is not None and s.section != section:
            continue
        mine = scores.get(s.usn, {})
        co_scores = {
            co: (mine[co].percentage if co in mine else None) for co in co_numbers
        }
        total_ob = sum(mine[co].obtained for co in co_numbers if co in mine)
        total_mx = sum(mine[co].maximum for co in co_numbers if co in mine)
        rows.append(
            SheetRow(
                usn=s.usn,
                name=s.name,
                section=s.section,
                co_scores=co_scores,
                total_obtained=total_ob,
                total_max=total_mx,
                total_pct=percentage(total_ob, total_mx),
            )
        )

    averages: dict[int, float | None] = {}
    for co in co_numbers:
        values = [r.co_scores[co] for r in rows if r.co_scores[co] is not None]
        averages[co] = sum(values) / len(values) if values else None
    return COSheet(co_numbers=co_numbers, rows=tuple(rows), averages=averages)


# -------------------------------------------------------------------------- summary


@dataclass(frozen=True)
class COSummary:
    co: int
    threshold_pct: float
    target_pct: float
    enrolled: int
    attempted: int  # students with a score for this CO
    not_attempted: int
    average: float | None
    above: int  # attempted students at or above the threshold
    below: int  # attempted students under the threshold
    attainment_pct: float | None
    met: bool  # attainment reached the target
    gap: float | None  # target - attainment; positive means short of target

    @property
    def has_data(self) -> bool:
        return self.attempted > 0


def class_summary(
    sheet: COSheet,
    cos: Sequence[COConfig],
    denominator: Literal["enrolled", "attempted"] = "enrolled",
) -> list[COSummary]:
    """Average, counts above and below threshold, and whether each CO met its target."""
    if denominator not in ("enrolled", "attempted"):
        raise ValueError("denominator must be 'enrolled' or 'attempted'")

    by_number = {c.number: c for c in cos}
    enrolled = len(sheet.rows)
    out: list[COSummary] = []
    for co in sheet.co_numbers:
        cfg = by_number[co]
        values = [r.co_scores[co] for r in sheet.rows if r.co_scores[co] is not None]
        above = sum(1 for v in values if meets_threshold(v, cfg.threshold_pct))
        attempted = len(values)
        base = enrolled if denominator == "enrolled" else attempted
        attainment = above * 100 / base if base else None
        met = attainment is not None and attainment >= cfg.target_pct - _EPSILON
        out.append(
            COSummary(
                co=co,
                threshold_pct=cfg.threshold_pct,
                target_pct=cfg.target_pct,
                enrolled=enrolled,
                attempted=attempted,
                not_attempted=enrolled - attempted,
                average=sheet.averages[co],
                above=above,
                below=attempted - above,
                attainment_pct=attainment,
                met=met,
                gap=None if attainment is None else cfg.target_pct - attainment,
            )
        )
    return out


@dataclass(frozen=True)
class WeakCO:
    co: int
    attainment_pct: float
    target_pct: float
    gap: float


def weak_cos(summary: Iterable[COSummary]) -> list[WeakCO]:
    """COs below target, biggest gap first.

    A CO that nobody has attempted yet is "no data", not weak, so it is not flagged.
    """
    weak = [
        WeakCO(s.co, s.attainment_pct, s.target_pct, s.gap)
        for s in summary
        if s.has_data and not s.met and s.attainment_pct is not None and s.gap is not None
    ]
    weak.sort(key=lambda w: (-w.gap, w.co))
    return weak


# ------------------------------------------------------------------------- drill-down


@dataclass(frozen=True)
class ModuleBreakdown:
    module_id: str
    obtained: float
    maximum: float
    students: int  # students with marks in this CO from this module

    @property
    def percentage(self) -> float | None:
        return percentage(self.obtained, self.maximum)


@dataclass(frozen=True)
class QuestionBreakdown:
    question_id: str
    module_id: str
    samples: int  # graded answers counted (under "average" both attempts count)
    correct: int

    @property
    def correct_pct(self) -> float | None:
        return percentage(self.correct, self.samples)


@dataclass(frozen=True)
class StudentBreakdown:
    usn: str
    name: str
    section: str | None
    obtained: float
    maximum: float
    attained: bool  # at or above the CO threshold

    @property
    def percentage(self) -> float | None:
        return percentage(self.obtained, self.maximum)


@dataclass(frozen=True)
class CODrilldown:
    co: int
    threshold_pct: float
    modules: tuple[ModuleBreakdown, ...]  # by module id
    questions: tuple[QuestionBreakdown, ...]  # hardest first (lowest correct rate)
    students: tuple[StudentBreakdown, ...]  # weakest first
    not_attempted: int  # rostered students in scope with no marks for this CO


def co_drilldown(
    counted: Iterable[CountedScore],
    roster: Iterable[StudentInfo],
    cfg: COConfig,
    module_id: str | None = None,
    section: str | None = None,
) -> CODrilldown:
    """The modules, questions and students behind one CO's number.

    Uses the same counted scores as the sheet, so the two always agree. Question
    results come from the counted attempts, so AttemptScore must have been built with
    from_grade (or with its questions filled in) for the question list to be filled.
    """
    co = cfg.number
    people = {s.usn: s for s in roster if section is None or s.section == section}

    by_module: dict[str, list[float]] = {}
    module_students: dict[str, set[str]] = {}
    by_student: dict[str, list[float]] = {}
    by_question: dict[tuple[str, str], list[int]] = {}  # [samples, correct]

    for c in counted:
        if c.usn not in people or co not in c.per_co:
            continue
        if module_id is not None and c.module_id != module_id:
            continue
        marks = c.per_co[co]

        cell = by_module.setdefault(c.module_id, [0.0, 0.0])
        cell[0] += marks.obtained
        cell[1] += marks.maximum
        module_students.setdefault(c.module_id, set()).add(c.usn)

        cell = by_student.setdefault(c.usn, [0.0, 0.0])
        cell[0] += marks.obtained
        cell[1] += marks.maximum

        for q in c.questions:
            if q.co != co:
                continue
            qcell = by_question.setdefault((c.module_id, q.question_id), [0, 0])
            qcell[0] += 1
            qcell[1] += 1 if q.is_correct else 0

    modules = tuple(
        ModuleBreakdown(m, ob, mx, len(module_students[m]))
        for m, (ob, mx) in sorted(by_module.items())
    )
    questions = tuple(
        sorted(
            (QuestionBreakdown(qid, m, n, ok) for (m, qid), (n, ok) in by_question.items()),
            key=lambda q: (q.correct_pct if q.correct_pct is not None else -1, q.module_id, q.question_id),
        )
    )
    students = []
    for usn, (ob, mx) in by_student.items():
        info = people[usn]
        pct = percentage(ob, mx)
        students.append(
            StudentBreakdown(usn, info.name, info.section, ob, mx, meets_threshold(pct, cfg.threshold_pct))
        )
    students.sort(key=lambda s: (s.percentage if s.percentage is not None else -1, s.usn))

    return CODrilldown(
        co=co,
        threshold_pct=cfg.threshold_pct,
        modules=modules,
        questions=questions,
        students=tuple(students),
        not_attempted=len(people) - len(by_student),
    )
