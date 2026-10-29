"""Development-only analytics data for the agent. Off by default.

Setting AGENT_DEV_IN_MEMORY_STORES=1 binds the three analytics agent tools to a small
synthetic dataset. The data does not match the database, so do not use the results to
judge real students. The server refuses to start with this flag when APP_ENV is production.
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

FLAG_NAME = "AGENT_DEV_IN_MEMORY_STORES"
PRODUCTION_ENVS = frozenset({"production", "prod"})
_warned = False


class DevStoreConfigurationError(RuntimeError):
    """The dev-only analytics data was enabled in an environment where it must not be."""


def dev_stores_enabled() -> bool:
    return os.getenv(FLAG_NAME, "").strip() == "1"


def validate_dev_store_config() -> None:
    """Called at startup so a bad combination fails fast, not on the first request."""
    env = os.getenv("APP_ENV", "").strip().lower()
    if dev_stores_enabled() and env in PRODUCTION_ENVS:
        raise DevStoreConfigurationError(
            f"{FLAG_NAME}=1 is not allowed when APP_ENV={env}. Unset the flag."
        )


def build_dev_analytics_store(connection: Any = None) -> Any | None:
    """Return a seeded in-memory analytics store, or None when the flag is off.

    The connection argument matches the production factory signature and is not used.
    """
    global _warned
    if not dev_stores_enabled():
        return None
    validate_dev_store_config()
    if not _warned:
        log.warning("Agent analytics use SYNTHETIC demo data because %s=1.", FLAG_NAME)
        _warned = True
    return _seed_store()


def _seed_store():
    # Imported here so that importing this module never depends on the engine code.
    from app.engine.co_math import AttemptScore, COConfig, COMarks, StudentInfo
    from app.services.co_analytics import InMemoryAnalyticsStore

    cos = [COConfig(1, 60.0, 60.0), COConfig(2, 60.0, 60.0), COConfig(3, 60.0, 60.0)]
    roster = [
        StudentInfo("DEV23CS001", "Demo Student One", "A"),
        StudentInfo("DEV23CS002", "Demo Student Two", "A"),
        StudentInfo("DEV23CS003", "Demo Student Three", "A"),
    ]
    # CO 3 is deliberately weak: none of the three students reaches the 60% threshold.
    attempts = [
        AttemptScore("DEV23CS001", "dev-quiz-1", "dev-module-1", 1,
                     {1: COMarks(1, 3, 3), 2: COMarks(2, 2, 2), 3: COMarks(3, 1, 3)}),
        AttemptScore("DEV23CS002", "dev-quiz-1", "dev-module-1", 1,
                     {1: COMarks(1, 2, 3), 2: COMarks(2, 2, 2), 3: COMarks(3, 0, 3)}),
        AttemptScore("DEV23CS003", "dev-quiz-1", "dev-module-1", 1,
                     {1: COMarks(1, 3, 3), 2: COMarks(2, 1, 2), 3: COMarks(3, 1, 3)}),
    ]
    co_id_map = {f"dev-co-{c.number}": c for c in cos}
    return InMemoryAnalyticsStore(cos=cos, roster=roster, attempts=attempts, co_id_map=co_id_map)


_dev_calendar_store: Any | None = None


def build_dev_calendar_store(connection: Any = None) -> Any | None:
    """Return one shared in-memory calendar store for development, or None when the flag is off.

    It is shared across requests, so a confirmed event shows up in the next list call. It
    resets when the server restarts, and it is refused in production like the analytics data.
    """
    global _dev_calendar_store
    if not dev_stores_enabled():
        return None
    validate_dev_store_config()
    if _dev_calendar_store is None:
        from app.services.calendar import InMemoryCalendarStore

        _dev_calendar_store = InMemoryCalendarStore()
    return _dev_calendar_store
