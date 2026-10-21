"""Shared test fixtures and helpers for backend tests."""
import os
import sys
import uuid
import secrets
import json
import types

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# Ensure project root is on sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend.app.main import app
from backend.app.db import get_engine
from backend.app.security import hash_password
from backend.app.deps import login_limiter


# ---------------------------------------------------------------------------
# Autouse: reset in-memory rate limiter between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    login_limiter.clear_all()
    yield
    login_limiter.clear_all()


# ---------------------------------------------------------------------------
# Engine / connection / client
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _engine():
    return get_engine()


@pytest.fixture
def db(_engine):
    """Raw database connection for setup and teardown."""
    conn = _engine.connect()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def client(db):
    """FastAPI TestClient (httpx-based)."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Unified test context with centralized cleanup
# ---------------------------------------------------------------------------

@pytest.fixture
def ctx(db, client):
    """Provides factory functions and handles all cleanup on teardown.

    Usage in tests::

        def test_x(client, ctx):
            faculty = ctx.make_faculty()
            subject = ctx.make_subject(faculty["user_id"])
            token = ctx.login(faculty["email"], faculty["password"])
            ...
    """
    # Ordered lists of IDs to delete
    cleanup = {
        "quizzes": [],
        "questions": [],
        "subjects": [],
        "students": [],       # student_id (UUID) to delete
        "usns": [],           # usn strings created by roster/confirm to delete
        "users": [],
        "custom": [],  # (sql, params) — runs first
    }

    # ---- Faculty ----
    def make_faculty(email=None, password="Pass1234", name=None):
        suffix = uuid.uuid4().hex[:8]
        email = email or f"fac_{suffix}@test.com"
        name = name or f"Faculty_{suffix}"
        pw_hash = hash_password(password)
        result = db.execute(
            text(
                "INSERT INTO users (role, email, name, password_hash) "
                "VALUES ('faculty', :email, :name, :hash) RETURNING id"
            ),
            {"email": email, "name": name, "hash": pw_hash},
        )
        user_id = str(result.mappings().fetchone()["id"])
        db.commit()
        cleanup["users"].append(user_id)
        # Also delete subjects owned by this faculty (in case make_subject cleanup misses some)
        cleanup["custom"].append((
            "DELETE FROM subjects WHERE faculty_user_id = :fid",
            {"fid": user_id},
        ))
        return {"user_id": user_id, "email": email, "password": password, "name": name}

    # ---- Student ----
    def make_student(usn=None, pin=None):
        suffix = uuid.uuid4().hex[:8]
        usn = usn or f"1AT0{suffix[:4]}".upper()
        pin = pin or str(secrets.randbelow(900000) + 100000)
        name = f"Student_{suffix}"
        pin_hash = hash_password(pin)

        result = db.execute(
            text(
                "INSERT INTO students (usn, name, pin_hash) "
                "VALUES (:usn, :name, :hash) RETURNING id"
            ),
            {"usn": usn, "name": name, "hash": pin_hash},
        )
        student_id = str(result.mappings().fetchone()["id"])

        db.execute(
            text("INSERT INTO users (role, student_id) VALUES ('student', :sid)"),
            {"sid": student_id},
        )
        db.commit()
        cleanup["students"].append(student_id)
        cleanup["usns"].append(usn)
        return {"student_id": student_id, "usn": usn, "pin": pin, "name": name}

    # ---- Subject ----
    def make_subject(faculty_user_id, code=None, name=None, semester=1,
                     target=60, threshold=60):
        suffix = uuid.uuid4().hex[:8]
        code = code or f"TEST{suffix[:6]}"
        name = name or f"Subject_{suffix}"
        result = db.execute(
            text(
                "INSERT INTO subjects (code, name, semester, faculty_user_id, "
                "target_attainment_pct, default_threshold_pct) "
                "VALUES (:code, :name, :sem, :fid, :target, :threshold) RETURNING id"
            ),
            {
                "code": code, "name": name, "sem": semester,
                "fid": faculty_user_id, "target": target, "threshold": threshold,
            },
        )
        subject_id = str(result.mappings().fetchone()["id"])
        db.commit()
        cleanup["subjects"].append(subject_id)
        return {
            "subject_id": subject_id, "code": code, "name": name,
            "semester": semester, "faculty_user_id": faculty_user_id,
        }

    # ---- CO ----
    def make_co(subject_id, number, description=None):
        desc = description or f"CO{number} - Mastery of topic"
        result = db.execute(
            text(
                "INSERT INTO course_outcomes (subject_id, number, description) "
                "VALUES (:sid, :num, :desc) RETURNING id"
            ),
            {"sid": subject_id, "num": number, "desc": desc},
        )
        co_id = str(result.mappings().fetchone()["id"])
        db.commit()
        return {"co_id": co_id, "subject_id": subject_id,
                "number": number, "description": desc}

    # ---- Module ----
    def make_module(subject_id, number=None, title=None):
        suffix = uuid.uuid4().hex[:6]
        number = number or (int(suffix[:2], 16) % 100 + 1)
        title = title or f"Module_{suffix}"
        result = db.execute(
            text(
                "INSERT INTO modules (subject_id, number, title) "
                "VALUES (:sid, :num, :title) RETURNING id"
            ),
            {"sid": subject_id, "num": number, "title": title},
        )
        module_id = str(result.mappings().fetchone()["id"])
        db.commit()
        return {"module_id": module_id, "subject_id": subject_id,
                "number": number, "title": title}

    # ---- Question ----
    def make_question(module_id, co_id, faculty_user_id=None, status="draft",
                      source="faculty", stem=None, correct_option=1,
                      opts=None):
        suffix = uuid.uuid4().hex[:6]
        stem = stem or f"Question stem {suffix}"
        opts = opts or ["Option A", "Option B", "Option C", "Option D"]
        result = db.execute(
            text(
                "INSERT INTO questions "
                "(module_id, co_id, stem, options, correct_option, marks, "
                "difficulty, bloom_level, status, source, created_by) "
                "VALUES "
                "(:mid, :cid, :stem, CAST(:opts AS jsonb), :co, "
                "1, 'medium', 'remember', :status, :source, :cb) "
                "RETURNING id"
            ),
            {
                "mid": module_id, "cid": co_id, "stem": stem,
                "opts": json.dumps(opts), "co": correct_option,
                "status": status, "source": source, "cb": faculty_user_id,
            },
        )
        qid = str(result.mappings().fetchone()["id"])
        db.commit()
        cleanup["questions"].append(qid)
        return {"question_id": qid, "module_id": module_id, "co_id": co_id,
                "stem": stem, "status": status, "source": source,
                "correct_option": correct_option, "options": opts}

    # ---- Enrollment ----
    def make_enrollment(student_id, subject_id, section="A"):
        db.execute(
            text(
                "INSERT INTO enrollments (student_id, subject_id, section) "
                "VALUES (:sid, :subj, :sec)"
            ),
            {"sid": student_id, "subj": subject_id, "sec": section},
        )
        db.commit()
        return {"student_id": student_id, "subject_id": subject_id, "section": section}

    # ---- Quiz (direct DB insert) ----
    def make_quiz(module_id, subject_id, title=None, published=False,
                  question_ids=None, faculty_user_id=None):
        suffix = uuid.uuid4().hex[:6]
        title = title or f"Quiz_{suffix}"
        result = db.execute(
            text(
                "INSERT INTO quizzes (module_id, subject_id, title, "
                "opens_at, closes_at, published, created_by) "
                "VALUES (:mid, :sid, :title, :opens, :closes, :pub, :cb) RETURNING id"
            ),
            {
                "mid": module_id, "sid": subject_id, "title": title,
                "opens": "2025-01-01T00:00:00Z",
                "closes": "2025-12-31T23:59:59Z",
                "pub": published, "cb": faculty_user_id,
            },
        )
        quiz_id = str(result.mappings().fetchone()["id"])
        for idx, qid in enumerate(question_ids or []):
            db.execute(
                text(
                    "INSERT INTO quiz_questions (quiz_id, question_id, position) "
                    "VALUES (:qid, :qid2, :pos)"
                ),
                {"qid": quiz_id, "qid2": qid, "pos": idx},
            )
        db.commit()
        cleanup["quizzes"].append(quiz_id)
        return {"quiz_id": quiz_id, "title": title, "subject_id": subject_id,
                "module_id": module_id, "published": published}

    # ---- Login helper ----
    def login(email=None, password=None, usn=None, pin=None):
        if email is not None:
            return client.post("/auth/login", json={"email": email, "password": password})
        return client.post("/auth/login", json={"usn": usn, "pin": pin})

    def headers(token):
        return {"Authorization": f"Bearer {token}"}

    def register_usn(usn):
        """Register a USN created by the roster endpoint so it gets cleaned up."""
        if usn and usn not in cleanup["usns"]:
            cleanup["usns"].append(usn)

    # ---- Assemble ----
    factories = types.SimpleNamespace(
        make_faculty=make_faculty,
        make_student=make_student,
        make_subject=make_subject,
        make_co=make_co,
        make_module=make_module,
        make_question=make_question,
        make_enrollment=make_enrollment,
        make_quiz=make_quiz,
        login=login,
        headers=headers,
        register_usn=register_usn,
    )

    yield factories

    # ---- Teardown (reverse FK order) ----
    # custom cleanup first (e.g., DELETE subjects by faculty_id)
    for sql, params in cleanup["custom"]:
        try:
            db.execute(text(sql), params)
        except Exception:
            pass
    # quizzes → quiz_questions and quiz_attempts (CASCADE)
    for qid in reversed(cleanup["quizzes"]):
        try:
            db.execute(text("DELETE FROM quizzes WHERE id = :id"), {"id": qid})
        except Exception:
            pass
    # questions (must be after quizzes because quiz_questions.question_id is RESTRICT)
    for qid in reversed(cleanup["questions"]):
        try:
            db.execute(text("DELETE FROM questions WHERE id = :id"), {"id": qid})
        except Exception:
            pass
    # subjects (CASCADE to cos, modules, enrollments)
    for sid in reversed(cleanup["subjects"]):
        try:
            db.execute(text("DELETE FROM subjects WHERE id = :id"), {"id": sid})
        except Exception:
            pass
    # students (CASCADE to enrollments, users)
    for sid in reversed(cleanup["students"]):
        try:
            db.execute(text("DELETE FROM students WHERE id = :id"), {"id": sid})
        except Exception:
            pass
    # Also delete students created by roster confirm (tracked by USN)
    for usn in reversed(cleanup["usns"]):
        try:
            db.execute(text("DELETE FROM students WHERE usn = :usn"), {"usn": usn})
        except Exception:
            pass
    # users (faculty) — must be after subjects
    for uid in reversed(cleanup["users"]):
        try:
            db.execute(text("DELETE FROM users WHERE id = :id"), {"id": uid})
        except Exception:
            pass
    db.commit()
