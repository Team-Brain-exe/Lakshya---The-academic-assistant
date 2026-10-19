from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request, Body

from ..db import get_conn
from ..deps import login_limiter
from ..errors import AppError
from ..security import create_token, verify_password, verify_pin, verify_dummy
from ..deps import get_current_user
from sqlalchemy import text

router = APIRouter(tags=["auth"])


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/auth/login")
def login(
    request: Request,
    conn=Depends(get_conn),
    payload: dict = Body(...),
):
    ip = _client_ip(request)
    usn = payload.get("usn")
    pin = payload.get("pin")
    email = payload.get("email")
    password = payload.get("password")

    # Determine login type
    if usn is not None and pin is not None:
        return _login_student(conn, usn, pin, ip)
    if email is not None and password is not None:
        return _login_faculty(conn, email, password, ip)

    raise AppError(401, "UNAUTHENTICATED", "Invalid credentials")


def _login_rate_key(identifier: str, ip: str) -> tuple[str, str]:
    return (identifier, ip)


def _login_student(conn, usn: str, pin: str, ip: str):
    # USN trimmed + uppercased
    norm_usn = usn.strip().upper()

    if login_limiter.is_limited(norm_usn, ip):
        raise AppError(429, "RATE_LIMITED", "Too many failed login attempts. Try again later.")

    row = conn.execute(
        text("SELECT id, usn, pin_hash FROM students WHERE usn = :usn"),
        {"usn": norm_usn},
    ).fetchone()

    # Always do a bcrypt comparison to prevent timing leaks
    if row is None:
        verify_dummy(pin)
        login_limiter.record_failure(norm_usn, ip)
        raise AppError(401, "UNAUTHENTICATED", "Invalid credentials")

    if not verify_pin(pin, row.pin_hash):
        login_limiter.record_failure(norm_usn, ip)
        raise AppError(401, "UNAUTHENTICATED", "Invalid credentials")

    # Load the matching users row (role student)
    user_row = conn.execute(
        text("SELECT id, role, name, student_id FROM users WHERE student_id = :sid"),
        {"sid": str(row.id)},
    ).fetchone()

    if user_row is None:
        login_limiter.record_failure(norm_usn, ip)
        raise AppError(401, "UNAUTHENTICATED", "Invalid credentials")

    login_limiter.reset(norm_usn, ip)

    token = create_token(
        user_id=str(user_row.id),
        role="student",
        student_id=str(row.id),
        usn=row.usn,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "student",
        "user": {
            "id": str(user_row.id),
            "name": user_row.name,
            "usn": row.usn,
            "email": None,
            "student_id": str(row.id),
        },
    }


def _login_faculty(conn, email: str, password: str, ip: str):
    norm_email = email.strip().lower()

    if login_limiter.is_limited(norm_email, ip):
        raise AppError(429, "RATE_LIMITED", "Too many failed login attempts. Try again later.")

    row = conn.execute(
        text(
            "SELECT id, role, name, email, password_hash "
            "FROM users WHERE email = :email AND role = 'faculty'"
        ),
        {"email": norm_email},
    ).fetchone()

    if row is None:
        verify_dummy(password)
        login_limiter.record_failure(norm_email, ip)
        raise AppError(401, "UNAUTHENTICATED", "Invalid credentials")

    if not verify_password(password, row.password_hash):
        login_limiter.record_failure(norm_email, ip)
        raise AppError(401, "UNAUTHENTICATED", "Invalid credentials")

    login_limiter.reset(norm_email, ip)

    token = create_token(
        user_id=str(row.id),
        role="faculty",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "faculty",
        "user": {
            "id": str(row.id),
            "name": row.name,
            "usn": None,
            "email": row.email,
        },
    }


# ---------------------------------------------------------------------------
# Me
# ---------------------------------------------------------------------------

@router.get("/auth/me")
def get_me(
    conn=Depends(get_conn),
    current_user=Depends(get_current_user),
):
    """Returns the authenticated user's profile."""
    role = current_user["role"]

    if role == "faculty":
        row = conn.execute(
            text("SELECT id, name, email FROM users WHERE id = :uid"),
            {"uid": current_user["user_id"]},
        ).fetchone()
        if row is None:
            raise AppError(404, "NOT_FOUND", "User not found")
        return {
            "id": str(row.id),
            "role": role,
            "name": row.name,
            "usn": None,
            "email": row.email,
        }

    # student
    row = conn.execute(
        text(
            "SELECT u.id, u.name, u.email, s.usn, s.id AS student_id "
            "FROM users u JOIN students s ON s.id = u.student_id "
            "WHERE u.id = :uid"
        ),
        {"uid": current_user["user_id"]},
    ).fetchone()
    if row is None:
        raise AppError(404, "NOT_FOUND", "User not found")
    return {
        "id": str(row.id),
        "role": role,
        "name": row.name,
        "usn": row.usn,
        "email": None,
        "student_id": str(row.student_id),
    }
