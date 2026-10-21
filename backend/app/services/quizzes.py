"""Quiz publishing, attempt management, and deterministic grading integration.

Enforces:
- Question approval check before publishing (refuses unapproved with QUESTION_NOT_APPROVED)
- Maximum 2 attempts per student per quiz (refuses with ATTEMPT_LIMIT_REACHED)
- Secret masking: correct_option and explanation are stripped before submission
- Grading through engine/grading.py and co_math.py
- StudentCOScore row persistence with ATTEMPT_RULE counted flag management
- Matching docs/api-contract.md section 7 and arya.md tasks 4 & 5.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol, Sequence

from app.engine.co_math import AttemptScore, select_counted
from app.engine.grading import QuestionKey, grade_attempt
from app.engine.settings import DEFAULT_ATTEMPT_RULE, DEFAULT_MAX_ATTEMPTS, load_grading_settings


# Contract error exceptions
class QuizError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class QuizNotPublishedError(QuizError):
    def __init__(self, message: str = "This quiz has not been published yet.") -> None:
        super().__init__("QUIZ_NOT_PUBLISHED", message, 409)


class QuizNotOpenError(QuizError):
    def __init__(self, message: str = "This quiz is not yet open.") -> None:
        super().__init__("QUIZ_NOT_OPEN", message, 409)


class QuizClosedError(QuizError):
    def __init__(self, message: str = "This quiz is closed.") -> None:
        super().__init__("QUIZ_CLOSED", message, 409)


class AttemptLimitReachedError(QuizError):
    def __init__(self, message: str = "You have used both attempts for this quiz.") -> None:
        super().__init__("ATTEMPT_LIMIT_REACHED", message, 409)


class QuestionNotApprovedError(QuizError):
    def __init__(self, message: str = "A quiz can only include approved questions.") -> None:
        super().__init__("QUESTION_NOT_APPROVED", message, 409)


class ForbiddenError(QuizError):
    def __init__(self, message: str = "Forbidden.") -> None:
        super().__init__("FORBIDDEN", message, 403)


class NotFoundError(QuizError):
    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__("NOT_FOUND", message, 404)


@dataclass(frozen=True)
class QuestionRecord:
    id: str
    module_id: str
    co_id: str
    co_number: int
    stem: str
    options: list[str]  # exactly 4 options
    correct_option: int  # 0..3
    explanation: str | None
    marks: float = 1.0
    difficulty: str | None = "medium"
    bloom_level: str | None = "understand"
    status: str = "draft"  # 'draft', 'approved', 'rejected'
    source: str = "faculty"  # 'faculty', 'AI'


@dataclass(frozen=True)
class QuizRecord:
    id: str
    module_id: str
    subject_id: str
    title: str
    question_ids: tuple[str, ...]
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    published: bool = False
    published_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class QuizAttemptRecord:
    id: str
    quiz_id: str
    student_id: str
    attempt_number: int  # 1 or 2
    answers: dict[str, int]
    total_score: float | None = None
    max_score: float | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: datetime | None = None


@dataclass(frozen=True)
class StudentCOScoreRecord:
    id: str
    student_id: str
    subject_id: str
    module_id: str
    co_id: str
    attempt_id: str
    marks_obtained: float
    max_marks: float
    percentage: float | None
    counted: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class QuizStore(Protocol):
    """Protocol for quiz, attempt, and score storage."""

    def save_quiz(self, quiz: QuizRecord) -> QuizRecord: ...

    def get_quiz(self, quiz_id: str) -> QuizRecord | None: ...

    def list_quizzes(self, subject_id: str) -> list[QuizRecord]: ...

    def get_question(self, question_id: str) -> QuestionRecord | None: ...

    def get_questions_for_quiz(self, quiz_id: str) -> list[QuestionRecord]: ...

    def save_attempt(self, attempt: QuizAttemptRecord) -> QuizAttemptRecord: ...

    def get_attempt(self, attempt_id: str) -> QuizAttemptRecord | None: ...

    def list_attempts(self, quiz_id: str, student_id: str) -> list[QuizAttemptRecord]: ...

    def save_co_scores(self, scores: Sequence[StudentCOScoreRecord]) -> None: ...

    def list_co_scores_for_student(self, student_id: str, subject_id: str) -> list[StudentCOScoreRecord]: ...

    def update_co_score_counted(self, attempt_id: str, counted: bool) -> None: ...


class InMemoryQuizStore:
    """In-memory store for unit tests and local mock execution."""

    def __init__(self) -> None:
        self.quizzes: dict[str, QuizRecord] = {}
        self.questions: dict[str, QuestionRecord] = {}
        self.attempts: dict[str, QuizAttemptRecord] = {}
        self.co_scores: dict[str, StudentCOScoreRecord] = {}

    def save_quiz(self, quiz: QuizRecord) -> QuizRecord:
        self.quizzes[quiz.id] = quiz
        return quiz

    def get_quiz(self, quiz_id: str) -> QuizRecord | None:
        return self.quizzes.get(quiz_id)

    def list_quizzes(self, subject_id: str) -> list[QuizRecord]:
        return [q for q in self.quizzes.values() if q.subject_id == subject_id]

    def add_question(self, q: QuestionRecord) -> None:
        self.questions[q.id] = q

    def get_question(self, question_id: str) -> QuestionRecord | None:
        return self.questions.get(question_id)

    def get_questions_for_quiz(self, quiz_id: str) -> list[QuestionRecord]:
        qz = self.quizzes.get(quiz_id)
        if not qz:
            return []
        return [self.questions[qid] for qid in qz.question_ids if qid in self.questions]

    def save_attempt(self, attempt: QuizAttemptRecord) -> QuizAttemptRecord:
        self.attempts[attempt.id] = attempt
        return attempt

    def get_attempt(self, attempt_id: str) -> QuizAttemptRecord | None:
        return self.attempts.get(attempt_id)

    def list_attempts(self, quiz_id: str, student_id: str) -> list[QuizAttemptRecord]:
        atts = [a for a in self.attempts.values() if a.quiz_id == quiz_id and a.student_id == student_id]
        atts.sort(key=lambda a: a.attempt_number)
        return atts

    def save_co_scores(self, scores: Sequence[StudentCOScoreRecord]) -> None:
        for s in scores:
            self.co_scores[s.id] = s

    def list_co_scores_for_student(self, student_id: str, subject_id: str) -> list[StudentCOScoreRecord]:
        return [s for s in self.co_scores.values() if s.student_id == student_id and s.subject_id == subject_id]

    def update_co_score_counted(self, attempt_id: str, counted: bool) -> None:
        for sid, sc in list(self.co_scores.items()):
            if sc.attempt_id == attempt_id:
                self.co_scores[sid] = StudentCOScoreRecord(
                    id=sc.id,
                    student_id=sc.student_id,
                    subject_id=sc.subject_id,
                    module_id=sc.module_id,
                    co_id=sc.co_id,
                    attempt_id=sc.attempt_id,
                    marks_obtained=sc.marks_obtained,
                    max_marks=sc.max_marks,
                    percentage=sc.percentage,
                    counted=counted,
                    created_at=sc.created_at,
                )


# --- Service Functions ---

def create_quiz(
    store: QuizStore,
    faculty_user: dict[str, Any],
    module_id: str,
    subject_id: str,
    title: str,
    question_ids: Sequence[str],
    *,
    opens_at: datetime | None = None,
    closes_at: datetime | None = None,
    quiz_id: str | None = None,
) -> QuizRecord:
    """Create a quiz draft. Faculty only."""
    if faculty_user.get("role") != "faculty":
        raise ForbiddenError("Only faculty can create quizzes.")

    if not question_ids:
        raise QuizError("BAD_REQUEST", "A quiz must have at least one question.", 400)

    # Verify questions exist
    for qid in question_ids:
        q = store.get_question(qid)
        if not q:
            raise NotFoundError(f"Question {qid} does not exist.")

    quiz = QuizRecord(
        id=quiz_id or str(uuid.uuid4()),
        module_id=module_id,
        subject_id=subject_id,
        title=title,
        question_ids=tuple(question_ids),
        opens_at=opens_at,
        closes_at=closes_at,
        published=False,
        created_by=faculty_user.get("user_id"),
    )
    return store.save_quiz(quiz)


def publish_quiz(
    store: QuizStore,
    faculty_user: dict[str, Any],
    quiz_id: str,
) -> QuizRecord:
    """Publish a quiz. Refuses if any question is not approved."""
    if faculty_user.get("role") != "faculty":
        raise ForbiddenError("Only faculty can publish quizzes.")

    quiz = store.get_quiz(quiz_id)
    if not quiz:
        raise NotFoundError(f"Quiz {quiz_id} not found.")

    questions = store.get_questions_for_quiz(quiz_id)
    if not questions:
        raise QuizError("BAD_REQUEST", "Quiz has no questions and cannot be published.", 400)

    # Check that ALL questions are approved
    for q in questions:
        if q.status != "approved":
            raise QuestionNotApprovedError(
                f"Question {q.id} is {q.status} (not approved) and cannot be published in a quiz."
            )

    published = QuizRecord(
        id=quiz.id,
        module_id=quiz.module_id,
        subject_id=quiz.subject_id,
        title=quiz.title,
        question_ids=quiz.question_ids,
        opens_at=quiz.opens_at,
        closes_at=quiz.closes_at,
        published=True,
        published_at=datetime.now(timezone.utc),
        created_by=quiz.created_by,
        created_at=quiz.created_at,
    )
    return store.save_quiz(published)


def list_quizzes(
    store: QuizStore,
    current_user: dict[str, Any],
    subject_id: str,
) -> list[dict[str, Any]]:
    """List quizzes. Students see published quizzes only, with attempts left."""
    role = current_user.get("role")
    student_id = current_user.get("student_id")
    quizzes = store.list_quizzes(subject_id)

    max_att = load_grading_settings().max_attempts
    out: list[dict[str, Any]] = []

    for q in quizzes:
        if role == "student" and not q.published:
            continue

        item: dict[str, Any] = {
            "id": q.id,
            "module_id": q.module_id,
            "subject_id": q.subject_id,
            "title": q.title,
            "opens_at": q.opens_at.isoformat() if q.opens_at else None,
            "closes_at": q.closes_at.isoformat() if q.closes_at else None,
            "published": q.published,
            "published_at": q.published_at.isoformat() if q.published_at else None,
            "question_count": len(q.question_ids),
        }

        if role == "student" and student_id:
            existing = store.list_attempts(q.id, student_id)
            used = len(existing)
            item["attempts_used"] = used
            item["attempts_left"] = max(0, max_att - used)

        out.append(item)
    return out


def _mask_questions_for_student(questions: Sequence[QuestionRecord]) -> list[dict[str, Any]]:
    """Strictly strip correct_option and explanation from questions shown to students."""
    return [
        {
            "id": q.id,
            "module_id": q.module_id,
            "co_id": q.co_id,
            "co_number": q.co_number,
            "stem": q.stem,
            "options": q.options,
            "marks": q.marks,
        }
        for q in questions
    ]


def start_quiz_attempt(
    store: QuizStore,
    student_user: dict[str, Any],
    quiz_id: str,
    *,
    now: datetime | None = None,
    attempt_id: str | None = None,
) -> dict[str, Any]:
    """Start an attempt. Student only. Enforces 2-attempt max and date windows."""
    if student_user.get("role") != "student":
        raise ForbiddenError("Only students can attempt quizzes.")

    student_id = student_user.get("student_id")
    if not student_id:
        raise ForbiddenError("Missing student_id for attempt.")

    quiz = store.get_quiz(quiz_id)
    if not quiz:
        raise NotFoundError("Quiz not found.")

    if not quiz.published:
        raise QuizNotPublishedError()

    curr_time = now or datetime.now(timezone.utc)
    if quiz.opens_at and curr_time < quiz.opens_at:
        raise QuizNotOpenError()
    if quiz.closes_at and curr_time > quiz.closes_at:
        raise QuizClosedError()

    existing_attempts = store.list_attempts(quiz_id, student_id)
    max_att = load_grading_settings().max_attempts
    if len(existing_attempts) >= max_att:
        raise AttemptLimitReachedError()

    next_num = len(existing_attempts) + 1
    attempt = QuizAttemptRecord(
        id=attempt_id or str(uuid.uuid4()),
        quiz_id=quiz_id,
        student_id=student_id,
        attempt_number=next_num,
        answers={},
        started_at=curr_time,
    )
    store.save_attempt(attempt)

    raw_questions = store.get_questions_for_quiz(quiz_id)
    masked_questions = _mask_questions_for_student(raw_questions)

    return {
        "attempt_id": attempt.id,
        "attempt_number": next_num,
        "attempts_left": max_att - next_num,
        "questions": masked_questions,
    }


def get_active_attempt(
    store: QuizStore,
    current_user: dict[str, Any],
    attempt_id: str,
) -> dict[str, Any]:
    """Resume an ongoing attempt. Student can only access their own attempt."""
    attempt = store.get_attempt(attempt_id)
    if not attempt:
        raise NotFoundError("Attempt not found.")

    student_id = current_user.get("student_id")
    if current_user.get("role") == "student" and attempt.student_id != student_id:
        raise ForbiddenError("You cannot view another student's attempt.")

    quiz = store.get_quiz(attempt.quiz_id)
    max_att = load_grading_settings().max_attempts
    raw_questions = store.get_questions_for_quiz(attempt.quiz_id)

    return {
        "attempt_id": attempt.id,
        "quiz_id": attempt.quiz_id,
        "attempt_number": attempt.attempt_number,
        "attempts_left": max(0, max_att - attempt.attempt_number),
        "status": "submitted" if attempt.submitted_at else "in_progress",
        "answers": attempt.answers,
        "questions": _mask_questions_for_student(raw_questions),
        "closes_at": quiz.closes_at.isoformat() if quiz and quiz.closes_at else None,
    }


def save_draft_answers(
    store: QuizStore,
    current_user: dict[str, Any],
    attempt_id: str,
    answers: dict[str, int],
) -> dict[str, Any]:
    """Autosave draft answers."""
    attempt = store.get_attempt(attempt_id)
    if not attempt:
        raise NotFoundError("Attempt not found.")

    student_id = current_user.get("student_id")
    if current_user.get("role") == "student" and attempt.student_id != student_id:
        raise ForbiddenError("You cannot edit another student's attempt.")

    if attempt.submitted_at is not None:
        raise QuizError("BAD_REQUEST", "Cannot modify answers of an already submitted attempt.", 400)

    updated = QuizAttemptRecord(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        student_id=attempt.student_id,
        attempt_number=attempt.attempt_number,
        answers=answers,
        started_at=attempt.started_at,
    )
    store.save_attempt(updated)
    return {"saved": True}


def submit_attempt(
    store: QuizStore,
    current_user: dict[str, Any],
    attempt_id: str,
    answers: dict[str, int],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Submit answers, compute deterministic grade, and persist StudentCOScore rows."""
    attempt = store.get_attempt(attempt_id)
    if not attempt:
        raise NotFoundError("Attempt not found.")

    student_id = current_user.get("student_id")
    if current_user.get("role") == "student" and attempt.student_id != student_id:
        raise ForbiddenError("You cannot submit another student's attempt.")

    if attempt.submitted_at is not None:
        raise QuizError("BAD_REQUEST", "Attempt is already submitted.", 400)

    quiz = store.get_quiz(attempt.quiz_id)
    if not quiz:
        raise NotFoundError("Quiz not found.")

    questions = store.get_questions_for_quiz(attempt.quiz_id)
    qkeys = [
        QuestionKey(
            id=q.id,
            co=q.co_number,
            correct_option=q.correct_option,
            marks=q.marks,
        )
        for q in questions
    ]

    # Deterministic grading
    grade = grade_attempt(qkeys, answers)
    submitted_time = now or datetime.now(timezone.utc)

    # Update attempt with score
    finished_attempt = QuizAttemptRecord(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        student_id=attempt.student_id,
        attempt_number=attempt.attempt_number,
        answers=answers,
        total_score=grade.total_obtained,
        max_score=grade.total_max,
        started_at=attempt.started_at,
        submitted_at=submitted_time,
    )
    store.save_attempt(finished_attempt)

    # Persist StudentCOScore rows
    new_co_scores = []
    for co_num, cm in grade.per_co.items():
        co_record = next((q.co_id for q in questions if q.co_number == co_num), None)
        if not co_record:
            continue
        new_co_scores.append(
            StudentCOScoreRecord(
                id=str(uuid.uuid4()),
                student_id=student_id,
                subject_id=quiz.subject_id,
                module_id=quiz.module_id,
                co_id=co_record,
                attempt_id=attempt.id,
                marks_obtained=cm.obtained,
                max_marks=cm.maximum,
                percentage=cm.percentage,
                counted=True,
                created_at=submitted_time,
            )
        )
    store.save_co_scores(new_co_scores)

    # Re-evaluate counted flags under ATTEMPT_RULE for this student and quiz
    _update_counted_flags(store, student_id, quiz)

    co_scores_res = [
        {
            "co_number": co_num,
            "marks": cm.obtained,
            "max": cm.maximum,
            "percentage": cm.percentage,
        }
        for co_num, cm in sorted(grade.per_co.items())
    ]

    return {
        "total_score": grade.total_obtained,
        "max_score": grade.total_max,
        "co_scores": co_scores_res,
    }


def _update_counted_flags(store: QuizStore, student_id: str, quiz: QuizRecord) -> None:
    """Re-evaluate and set counted flags when student attempts multiple times."""
    attempts = store.list_attempts(quiz.id, student_id)
    submitted = [a for a in attempts if a.submitted_at is not None]
    if len(submitted) <= 1:
        return

    # Build AttemptScore objects
    questions = store.get_questions_for_quiz(quiz.id)
    qkeys = [QuestionKey(q.id, q.co_number, q.correct_option, q.marks) for q in questions]

    attempt_scores: list[AttemptScore] = []
    for a in submitted:
        gr = grade_attempt(qkeys, a.answers)
        attempt_scores.append(
            AttemptScore.from_grade("student", quiz.id, quiz.module_id, a.attempt_number, gr)
        )

    rule = load_grading_settings().attempt_rule
    counted = select_counted(attempt_scores, rule)
    if not counted:
        return

    chosen_attempt_num = 1
    if rule == "latest":
        chosen_attempt_num = max(a.attempt_number for a in submitted)
    elif rule == "best":
        best_attempt = max(submitted, key=lambda a: (a.total_score or 0, a.attempt_number))
        chosen_attempt_num = best_attempt.attempt_number

    for a in submitted:
        is_counted = (a.attempt_number == chosen_attempt_num) if rule != "average" else True
        store.update_co_score_counted(a.id, is_counted)


def review_attempt(
    store: QuizStore,
    current_user: dict[str, Any],
    attempt_id: str,
) -> list[dict[str, Any]]:
    """Review submitted attempt. Reveals correct answer and explanation. Student only (own attempt)."""
    attempt = store.get_attempt(attempt_id)
    if not attempt:
        raise NotFoundError("Attempt not found.")

    student_id = current_user.get("student_id")
    if current_user.get("role") == "student" and attempt.student_id != student_id:
        raise ForbiddenError("You cannot review another student's attempt.")

    if attempt.submitted_at is None:
        raise QuizError("BAD_REQUEST", "Review is only available after attempt is submitted.", 400)

    questions = store.get_questions_for_quiz(attempt.quiz_id)
    review_items = []
    for q in questions:
        chosen = attempt.answers.get(q.id)
        review_items.append({
            "question_id": q.id,
            "question": q.stem,
            "options": q.options,
            "chosen": chosen,
            "correct": q.correct_option,
            "co_number": q.co_number,
            "explanation": q.explanation,
        })
    return review_items

