import pytest

from ai.agent import ToolValidationError, validate_json_schema
from ai.tool_contracts import ToolManifestError, build_tool_registry, load_tool_manifest


def test_tool_contracts_separate_student_and_faculty_progress_schemas():
    specs = {spec["name"]: spec for spec in load_tool_manifest()}

    student_props = specs["get_my_progress"]["parameters"]["properties"]
    faculty_props = specs["get_student_progress"]["parameters"]["properties"]
    assert "usn" not in student_props
    assert "usn" in faculty_props
    assert specs["propose_schedule_event"]["mutation"] == "confirm"
    assert specs["generate_quiz"]["mutation"] == "draft_review"


def test_registry_exposes_only_bound_tools_for_authenticated_role():
    registry = build_tool_registry({
        "answer_course_question": lambda args, user: {"answer": "Grounded"},
        "generate_quiz": lambda args, user: {"drafts": []},
    })

    student_names = {tool.name for tool in registry.for_role("student")}
    faculty_names = {tool.name for tool in registry.for_role("faculty")}
    assert "answer_course_question" in student_names
    assert "generate_quiz" not in student_names
    assert "generate_quiz" in faculty_names
    assert "find_weak_COs" not in faculty_names  # no handler, never advertise a stub


def test_registry_can_be_strict_when_server_adapters_are_expected():
    with pytest.raises(ToolManifestError, match="Handlers are not configured"):
        build_tool_registry({}, strict=True)


def test_date_time_schema_requires_timezone_and_accepts_null_optional_time():
    schema = {
        "type": "object",
        "properties": {
            "starts_at": {"type": "string", "format": "date-time"},
            "ends_at": {"type": ["string", "null"], "format": "date-time"},
        },
        "required": ["starts_at"],
        "additionalProperties": False,
    }

    validate_json_schema({"starts_at": "2030-01-15T10:00:00Z", "ends_at": None}, schema)
    with pytest.raises(ToolValidationError, match="timezone"):
        validate_json_schema({"starts_at": "2030-01-15T10:00:00"}, schema)
