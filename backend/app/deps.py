import time
from collections import defaultdict
from typing import Optional

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .errors import AppError
from .security import decode_token
from .db import get_conn
from sqlalchemy import text

bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# In-memory rate limiter for login failures
# ---------------------------------------------------------------------------

class LoginRateLimiter:
    """5 failures per 15 minutes, keyed by both identifier (USN or email)
    and by IP address."""

    max_failures = 5
    window_seconds = 15 * 60

    def __init__(self):
        self._by_key: dict[tuple[str, str], list[float]] = defaultdict(list)

    def _prune(self, key: tuple[str, str], now: float) -> list[float]:
        timestamps = self._by_key.get(key, [])
        recent = [t for t in timestamps if now - t < self.window_seconds]
        self._by_key[key] = recent
        return recent

    def is_limited(self, identifier: str, ip: str) -> bool:
        now = time.time()
        key = (identifier.lower(), ip)
        return len(self._prune(key, now)) >= self.max_failures

    def record_failure(self, identifier: str, ip: str) -> None:
        now = time.time()
        key = (identifier.lower(), ip)
        self._by_key[key].append(now)

    def reset(self, identifier: str, ip: str) -> None:
        key = (identifier.lower(), ip)
        self._by_key.pop(key, None)

    def clear_all(self) -> None:
        self._by_key.clear()


login_limiter = LoginRateLimiter()


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> dict:
    if credentials is None:
        raise AppError(401, "UNAUTHENTICATED", "Missing or invalid Authorization header")
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except Exception:
        raise AppError(401, "UNAUTHENTICATED", "Invalid or expired token")
    return {
        "user_id": payload["sub"],
        "role": payload["role"],
        "student_id": payload.get("student_id"),
        "usn": payload.get("usn"),
    }


def require_faculty(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "faculty":
        raise AppError(403, "FORBIDDEN", "Faculty access required")
    return user


def require_student(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "student":
        raise AppError(403, "FORBIDDEN", "Student access required")
    return user
