"""get_my_progress binding. Stand-in tools record what they receive; no database."""
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field, ValidationError

from app.errors import AppError
from app.services.agent_bindings import bind_student_self_progress


class GetStudentProgressArgs(BaseModel):
    subject_id: str = Field(...)
    usn: str | None = None


def fake_tools():
    calls = []

    def get_student_progress(args, user, store):
        calls.append((args, user, store))
        return {"usn": args.usn}

    tools = SimpleNamespace(GetStudentProgressArgs=GetStudentProgressArgs, get_student_progress=get_student_progress)
    return tools, calls


STUDENT = {"user_id": "s1", "role": "student", "usn": "1JT24CS001"}


def bound(store="STORE"):
    tools, calls = fake_tools()
    handlers = {}
    bind_student_self_progress(handlers, tools, store)
    return handlers["get_my_progress"], calls


def test_usn_comes_from_the_session_not_the_model():
    handler, calls = bound()
    result = handler({"subject_id": "subj-1", "usn": "1JT24CS999"}, STUDENT)
    args, user, store = calls[0]
    assert args.usn == "1JT24CS001"
    assert result == {"usn": "1JT24CS001"}
    assert user is STUDENT and store == "STORE"


def test_student_without_a_usn_is_refused():
    handler, calls = bound()
    with pytest.raises(AppError) as info:
        handler({"subject_id": "subj-1"}, {"role": "student", "user_id": "s1"})
    assert info.value.code == "FORBIDDEN"
    assert calls == []


def test_faculty_cannot_use_the_self_tool():
    handler, calls = bound()
    with pytest.raises(AppError):
        handler({"subject_id": "subj-1"}, {"role": "faculty", "user_id": "f1", "usn": None})
    assert calls == []


def test_missing_subject_is_rejected_before_the_store_is_used():
    handler, calls = bound()
    with pytest.raises(ValidationError):
        handler({}, STUDENT)
    assert calls == []
