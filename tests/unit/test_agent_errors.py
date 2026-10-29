"""Tests for turning AppError into a tool result. No database and no model."""
import pytest

from app.errors import AppError
from app.services.agent_errors import report_app_errors


def test_app_error_becomes_a_tool_result_with_code_and_message():
    def tool(args, current_user):
        raise AppError(403, "FORBIDDEN", "Only faculty can view this.")

    result = report_app_errors(tool)({}, {"role": "student"})
    assert result == {"error": {"code": "FORBIDDEN", "message": "Only faculty can view this."}}


def test_details_are_included_only_when_set():
    def tool(args, current_user):
        raise AppError(422, "INVALID", "Bad input", details={"field": "starts_at"})

    result = report_app_errors(tool)({}, {})
    assert result["error"]["details"] == {"field": "starts_at"}


def test_app_error_without_details_has_no_details_key():
    def tool(args, current_user):
        raise AppError(404, "NOT_FOUND", "No such subject.")

    assert "details" not in report_app_errors(tool)({}, {})["error"]


def test_other_exceptions_still_propagate():
    def tool(args, current_user):
        raise ValueError("unexpected")

    with pytest.raises(ValueError):
        report_app_errors(tool)({}, {})


def test_successful_results_pass_through_unchanged():
    def tool(args, current_user):
        return {"weak_cos": [3]}

    assert report_app_errors(tool)({}, {}) == {"weak_cos": [3]}


def test_wrapper_keeps_the_handler_name():
    def find_weak_cos(args, current_user):
        return {}

    assert report_app_errors(find_weak_cos).__name__ == "find_weak_cos"
