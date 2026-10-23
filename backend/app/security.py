import bcrypt
import jwt
from datetime import datetime, timedelta, timezone

from .config import SESSION_SECRET

# 8-hour expiry
TOKEN_EXPIRY_HOURS = 8
_ALGORITHM = "HS256"

# Pre-computed dummy hash for timing-attack-safe login failures.
_DUMMY_HASH = bcrypt.hashpw(b"dummy_password", bcrypt.gensalt()).decode("utf-8")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def verify_pin(pin: str, pin_hash: str) -> bool:
    """Verify a 6-digit PIN against its bcrypt hash."""
    return verify_password(pin, pin_hash)


def verify_dummy(password: str) -> bool:
    """Always-false verification against a dummy hash, used when the user
    does not exist so the response time matches a real failed login."""
    return verify_password(password, _DUMMY_HASH)


def create_token(
    user_id: str,
    role: str,
    student_id: str | None = None,
    usn: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(hours=TOKEN_EXPIRY_HOURS),
    }
    if student_id is not None:
        payload["student_id"] = student_id
    if usn is not None:
        payload["usn"] = usn
    return jwt.encode(payload, SESSION_SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.InvalidTokenError on failure."""
    return jwt.decode(token, SESSION_SECRET, algorithms=[_ALGORITHM], leeway=10)
