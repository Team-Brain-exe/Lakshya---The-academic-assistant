"""Usage tracking and token-cost endpoints.

Section 12 of docs/api-contract.md:
- GET /usage/summary
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.usage import UsageStore, get_usage_summary

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, status
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


def format_error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


class UsageRouterHandler:
    def __init__(self, store: UsageStore) -> None:
        self.store = store

    def get_summary(
        self,
        current_user: dict[str, Any],
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        if current_user.get("role") != "faculty":
            return 403, [format_error("FORBIDDEN", "Only faculty can view token usage and cost summaries.")]

        summary = get_usage_summary(self.store, from_time=from_time, to_time=to_time)
        return 200, summary


# ---------------------------------------------------------------------------
# Live route (Postgres)
# ---------------------------------------------------------------------------

from ..db import get_conn
from ..deps import require_faculty
from ..pg.usage import PostgresUsageStore

router = APIRouter(tags=["usage"])


@router.get("/usage/summary")
def usage_summary(
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    conn=Depends(get_conn),
    user=Depends(require_faculty),
):
    return PostgresUsageStore(conn).summary(from_, to)
