"""Schedule confirmation executor. The calendar function is a fake; no database."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.errors import AppError
from app.services.agent_executors import make_schedule_executor

FACULTY = {"user_id": "f1", "role": "faculty"}
ARGS = {"subject_id": "subj-1", "type": "quiz", "title": "CO3 review", "starts_at": "2026-10-27T10:00:00+05:30"}
IST = timezone(timedelta(hours=5, minutes=30))


class FakeCalendar:
    def __init__(self):
        self.calls = []

    def create_event(self, store, current_user, subject_id, event_type, title, starts_at, *,
                     ends_at=None, section=None, quiz_id=None, module_id=None,
                     created_by_agent=False, event_id=None):
        self.calls.append({"store": store, "starts_at": starts_at, "ends_at": ends_at,
                           "created_by_agent": created_by_agent, "event_type": event_type})
        return SimpleNamespace(to_dict=lambda: {"id": "e1", "title": title})


def make(calendar):
    return make_schedule_executor("STORE", calendar.create_event)


def test_faculty_confirm_creates_the_event_with_aware_times_marked_as_agent():
    calendar = FakeCalendar()
    result = make(calendar)(ARGS, FACULTY)
    assert result == {"id": "e1", "title": "CO3 review"}
    call = calendar.calls[0]
    assert call["starts_at"] == datetime(2026, 10, 27, 10, 0, tzinfo=IST)
    assert call["created_by_agent"] is True
    assert call["event_type"] == "quiz"
    assert call["store"] == "STORE"


def test_end_time_is_parsed_when_given():
    calendar = FakeCalendar()
    make(calendar)({**ARGS, "ends_at": "2026-10-27T11:00:00+05:30"}, FACULTY)
    assert calendar.calls[0]["ends_at"] == datetime(2026, 10, 27, 11, 0, tzinfo=IST)


def test_naive_start_time_is_refused_and_nothing_is_created():
    calendar = FakeCalendar()
    with pytest.raises(AppError) as info:
        make(calendar)({**ARGS, "starts_at": "2026-10-27T10:00:00"}, FACULTY)
    assert info.value.code == "INVALID_TIME"
    assert calendar.calls == []


def test_unparseable_time_is_refused():
    calendar = FakeCalendar()
    with pytest.raises(AppError) as info:
        make(calendar)({**ARGS, "starts_at": "tomorrow"}, FACULTY)
    assert info.value.code == "INVALID_TIME"
    assert calendar.calls == []


def test_student_cannot_run_the_executor():
    calendar = FakeCalendar()
    with pytest.raises(AppError) as info:
        make(calendar)(ARGS, {"user_id": "s1", "role": "student"})
    assert info.value.code == "FORBIDDEN"
    assert calendar.calls == []


def test_unknown_event_type_is_rejected():
    calendar = FakeCalendar()
    with pytest.raises(ValidationError):
        make(calendar)({**ARGS, "type": "party"}, FACULTY)
    assert calendar.calls == []
