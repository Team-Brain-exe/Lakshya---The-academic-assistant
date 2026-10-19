from enum import Enum
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class AppError(Exception):
    """Application-level error that maps to a known HTTP code and error code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_response(exc: AppError):
    body: dict[str, Any] = {"error": {"code": exc.code, "message": exc.message}}
    if exc.details is not None:
        body["error"]["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=body)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc)


def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", []))
        fields.append({"field": loc, "message": err.get("msg", "")})
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request body or query failed validation",
                "details": {"fields": fields},
            }
        },
    )


def integrity_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Map psycopg/SQLAlchemy integrity errors to contract error codes."""
    import psycopg.errors

    # sqlalchemy.exc.IntegrityError wraps the DBAPI error in .orig
    orig = getattr(exc, "orig", exc)
    pg_err = orig if isinstance(orig, Exception) else exc

    sqlstate = getattr(pg_err, "sqlstate", None)
    msg = str(pg_err)
    msg_lower = msg.lower()

    # 23505: unique violation -> CONFLICT
    if sqlstate == "23505":
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "CONFLICT",
                    "message": "A record with this value already exists",
                },
            },
        )

    # 23514: check violation
    if sqlstate == "23514":
        # Approval-triggers raise messages containing these keywords
        trigger_keywords = ("approved", "published quiz", "un-approved", "cannot be added to a quiz",
                            "cannot be published")
        if any(kw in msg_lower for kw in trigger_keywords):
            return JSONResponse(
                status_code=409,
                content={
                    "error": {
                        "code": "QUESTION_NOT_APPROVED",
                        "message": "One or more questions are not approved for this quiz",
                    },
                },
            )
        # Other check violations are validation errors
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Value failed a database constraint",
                    "details": {"constraint": msg},
                },
            },
        )

    # Any other database error -> 500 INTERNAL_ERROR
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected database error occurred",
            },
        },
    )


def unexpected_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Catch-all that never leaks a stack trace."""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            },
        },
    )
