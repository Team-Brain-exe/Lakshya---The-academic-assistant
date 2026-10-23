"""Quizzes and attempts endpoints.

Section 7 of docs/api-contract.md:
- POST /quizzes
- POST /quizzes/{id}/publish
- GET /quizzes?subject_id=
- POST /quizzes/{id}/attempts
- GET /attempts/{id}
- PUT /attempts/{id}/answers
- POST /attempts/{id}/submit
- GET /attempts/{id}/review
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from app.services.calendar import CalendarStore, auto_create_quiz_event
from app.services.quizzes import (
    AttemptLimitReachedError,
    ForbiddenError,
    NotFoundError,
    QuestionNotApprovedError,
    QuizClosedError,
    QuizError,
    QuizNotOpenError,
    QuizNotPublishedError,
    QuizStore,
    create_quiz,
    get_active_attempt,
    list_quizzes,
    publish_quiz,
    review_attempt,
    save_draft_answers,
    start_quiz_attempt,
    submit_attempt,
)

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, status
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


def format_error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


class QuizRouterHandler:
    def __init__(self, quiz_store: QuizStore, calendar_store: CalendarStore | None = None) -> None:
        self.quiz_store = quiz_store
        self.calendar_store = calendar_store

    def create(
        self,
        current_user: dict[str, Any],
        module_id: str,
        subject_id: str,
        title: str,
        question_ids: Sequence[str],
        opens_at: datetime | None = None,
        closes_at: datetime | None = None,
    ) -> tuple[int, dict[str, Any]]:
        try:
            quiz = create_quiz(
                self.quiz_store,
                current_user,
                module_id=module_id,
                subject_id=subject_id,
                title=title,
                question_ids=question_ids,
                opens_at=opens_at,
                closes_at=closes_at,
            )
            return 201, {
                "id": quiz.id,
                "module_id": quiz.module_id,
                "subject_id": quiz.subject_id,
                "title": quiz.title,
                "opens_at": quiz.opens_at.isoformat() if quiz.opens_at else None,
                "closes_at": quiz.closes_at.isoformat() if quiz.closes_at else None,
                "published": quiz.published,
                "published_at": quiz.published_at.isoformat() if quiz.published_at else None,
                "question_count": len(quiz.question_ids),
            }
        except QuizError as exc:
            return exc.status_code, format_error(exc.code, exc.message)

    def publish(
        self,
        current_user: dict[str, Any],
        quiz_id: str,
    ) -> tuple[int, dict[str, Any]]:
        try:
            quiz = publish_quiz(self.quiz_store, current_user, quiz_id)
            event_id = None
            if self.calendar_store and quiz.opens_at:
                ev = auto_create_quiz_event(
                    self.calendar_store,
                    current_user,
                    quiz.subject_id,
                    quiz.id,
                    quiz.title,
                    quiz.opens_at,
                    quiz.closes_at,
                )
                event_id = ev.id

            res = {
                "id": quiz.id,
                "module_id": quiz.module_id,
                "subject_id": quiz.subject_id,
                "title": quiz.title,
                "opens_at": quiz.opens_at.isoformat() if quiz.opens_at else None,
                "closes_at": quiz.closes_at.isoformat() if quiz.closes_at else None,
                "published": quiz.published,
                "published_at": quiz.published_at.isoformat() if quiz.published_at else None,
                "question_count": len(quiz.question_ids),
                "event_id": event_id,
            }
            return 200, res
        except QuizError as exc:
            return exc.status_code, format_error(exc.code, exc.message)

    def list_for_subject(
        self,
        current_user: dict[str, Any],
        subject_id: str,
    ) -> tuple[int, list[dict[str, Any]]]:
        quizzes = list_quizzes(self.quiz_store, current_user, subject_id)
        return 200, quizzes

    def start_attempt(
        self,
        current_user: dict[str, Any],
        quiz_id: str,
        *,
        now: datetime | None = None,
    ) -> tuple[int, dict[str, Any]]:
        try:
            res = start_quiz_attempt(self.quiz_store, current_user, quiz_id, now=now)
            return 201, res
        except QuizError as exc:
            return exc.status_code, format_error(exc.code, exc.message)

    def get_attempt_state(
        self,
        current_user: dict[str, Any],
        attempt_id: str,
    ) -> tuple[int, dict[str, Any]]:
        try:
            res = get_active_attempt(self.quiz_store, current_user, attempt_id)
            return 200, res
        except QuizError as exc:
            return exc.status_code, format_error(exc.code, exc.message)

    def save_answers(
        self,
        current_user: dict[str, Any],
        attempt_id: str,
        answers: dict[str, int],
    ) -> tuple[int, dict[str, Any]]:
        try:
            res = save_draft_answers(self.quiz_store, current_user, attempt_id, answers)
            return 200, res
        except QuizError as exc:
            return exc.status_code, format_error(exc.code, exc.message)

    def submit(
        self,
        current_user: dict[str, Any],
        attempt_id: str,
        answers: dict[str, int],
    ) -> tuple[int, dict[str, Any]]:
        try:
            res = submit_attempt(self.quiz_store, current_user, attempt_id, answers)
            return 200, res
        except QuizError as exc:
            return exc.status_code, format_error(exc.code, exc.message)

    def review(
        self,
        current_user: dict[str, Any],
        attempt_id: str,
    ) -> tuple[int, Any]:
        try:
            res = review_attempt(self.quiz_store, current_user, attempt_id)
            return 200, res
        except QuizError as exc:
            return exc.status_code, format_error(exc.code, exc.message)


router = APIRouter() if HAS_FASTAPI else None

