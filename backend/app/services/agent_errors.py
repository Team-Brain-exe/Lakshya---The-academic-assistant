"""Turn a backend AppError into a tool result the model can read.

Only AppError is converted. Any other exception still propagates, so the agent loop's
generic handler logs it and the model receives a neutral failure message.
"""
from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any

from ..errors import AppError

log = logging.getLogger(__name__)


def app_error_payload(exc: AppError) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": exc.code, "message": exc.message}
    if getattr(exc, "details", None) is not None:
        payload["details"] = exc.details
    return {"error": payload}


def report_app_errors(handler: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a tool handler so AppError becomes {"error": {...}} instead of a generic failure."""

    @functools.wraps(handler)
    def wrapped(args: dict[str, Any], current_user: dict[str, Any]) -> Any:
        try:
            return handler(args, current_user)
        except AppError as exc:
            # Log the code only, never the arguments or the user.
            log.info("agent tool refused with code %s (HTTP %s)", exc.code, exc.status_code)
            return app_error_payload(exc)

    return wrapped
