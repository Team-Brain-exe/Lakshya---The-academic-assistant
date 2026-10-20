"""Grading configuration, read from environment variables.

ATTEMPT_RULE decides which attempt counts when a student attempts a quiz twice:
  best    the attempt with the highest total score (tie: the later attempt)
  latest  the attempt with the highest attempt number
  average the mean of all attempts, per CO

Default is "best" until faculty confirm (see docs/decisions.md).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

VALID_ATTEMPT_RULES = ("best", "latest", "average")
DEFAULT_ATTEMPT_RULE = "best"
DEFAULT_MAX_ATTEMPTS = 2


@dataclass(frozen=True)
class GradingSettings:
    attempt_rule: str = DEFAULT_ATTEMPT_RULE
    max_attempts: int = DEFAULT_MAX_ATTEMPTS

    def __post_init__(self) -> None:
        if self.attempt_rule not in VALID_ATTEMPT_RULES:
            raise ValueError(
                f"ATTEMPT_RULE must be one of {VALID_ATTEMPT_RULES}, got {self.attempt_rule!r}"
            )
        if self.max_attempts < 1:
            raise ValueError(f"MAX_ATTEMPTS must be at least 1, got {self.max_attempts}")


def load_grading_settings(env: dict[str, str] | None = None) -> GradingSettings:
    """Build settings from the environment. Empty values fall back to the defaults."""
    source = os.environ if env is None else env
    rule = (source.get("ATTEMPT_RULE") or DEFAULT_ATTEMPT_RULE).strip().lower()
    raw_max = (source.get("MAX_ATTEMPTS") or str(DEFAULT_MAX_ATTEMPTS)).strip()
    try:
        max_attempts = int(raw_max)
    except ValueError:
        raise ValueError(f"MAX_ATTEMPTS must be a whole number, got {raw_max!r}") from None
    return GradingSettings(attempt_rule=rule, max_attempts=max_attempts)
