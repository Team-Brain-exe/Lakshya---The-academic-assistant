"""Tool bindings that need a server-held store or the caller's session identity.

Identity always comes from the session. The model's arguments are rebuilt from scratch,
so any extra field it sends (including a usn) is dropped.
"""
from __future__ import annotations

from typing import Any

from ..errors import AppError


def bind_student_self_progress(handlers: dict[str, Any], agent_tools: Any, store: Any) -> None:
    """Bind get_my_progress: the caller's own CO progress, using the USN from the session."""

    def my_progress(args: dict[str, Any], current_user: dict[str, Any]) -> Any:
        if current_user.get("role") != "student":
            raise AppError(403, "FORBIDDEN", "Only students can use this tool.")
        usn = current_user.get("usn")
        if not usn:
            raise AppError(403, "FORBIDDEN", "This session has no student record.")
        validated = agent_tools.GetStudentProgressArgs.model_validate(
            {"subject_id": args.get("subject_id"), "usn": usn}
        )
        return agent_tools.get_student_progress(validated, current_user, store)

    handlers["get_my_progress"] = my_progress
