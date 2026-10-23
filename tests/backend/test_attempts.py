"""Tests for quiz attempt endpoints (contract section 7, Part A).

Covers: start, resume, saved answers persist, submit returns scores and
writes student_co_scores rows, both attempts allowed and third refused,
closed and not-open quizzes, masking of correct answers, and cross-student
access.
"""
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from backend.app.db import get_engine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc)


def _make_published_open_quiz(
    db, ctx, faculty, *,
    opens_at=None, closes_at=None,
    question_ids=None, title="Test Quiz",
):
    """Create a published, currently-open quiz with two approved questions
    spanning two COs.  Returns a dict with quiz_id, question_keys, correct
    answers, and subject/module/co_ids for assertions and cleanup.
    """
    subj = ctx.make_subject(faculty["user_id"])
    co1 = ctx.make_co(subj["subject_id"], 1, "CO1 - Topic A")
    co2 = ctx.make_co(subj["subject_id"], 2, "CO2 - Topic B")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    q1 = ctx.make_question(
        mod["module_id"], co1["co_id"],
        faculty_user_id=faculty["user_id"], status="approved",
        stem="Question one", correct_option=0,
        opts=["A", "B", "C", "D"],
    )
    q2 = ctx.make_question(
        mod["module_id"], co2["co_id"],
        faculty_user_id=faculty["user_id"], status="approved",
        stem="Question two", correct_option=1,
        opts=["A", "B", "C", "D"],
    )
    qkids = question_ids or [q1["question_id"], q2["question_id"]]

    now = _now()
    opens = opens_at if opens_at is not None else (now - timedelta(hours=1))
    closes = closes_at if closes_at is not None else (now + timedelta(hours=1))

    quiz = ctx.make_quiz(
        mod["module_id"], subj["subject_id"],
        faculty_user_id=faculty["user_id"], title=title,
        question_ids=qkids,
    )
    db.execute(
        text(
            "UPDATE quizzes SET opens_at = :opens, closes_at = :closes, "
            "published = true, published_at = now() WHERE id = :id"
        ),
        {"opens": opens, "closes": closes, "id": quiz["quiz_id"]},
    )
    db.commit()

    return {
        "quiz_id": quiz["quiz_id"],
        "question_keys": [q1["question_id"], q2["question_id"]],
        "correct": {q1["question_id"]: 0, q2["question_id"]: 1},
        "subject_id": subj["subject_id"],
        "module_id": mod["module_id"],
        "co_ids": [co1["co_id"], co2["co_id"]],
    }


def _start_attempt(client, headers, quiz_id):
    """POST /quizzes/{id}/attempts and return (attempt_id, question_ids)."""
    resp = client.post(f"/quizzes/{quiz_id}/attempts", headers=headers)
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    q_ids = [q["id"] for q in body["questions"]]
    return body["attempt_id"], q_ids


def _submit(client, headers, attempt_id, answers):
    return client.post(
        f"/attempts/{attempt_id}/submit", headers=headers,
        json={"answers": answers},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_start_attempt_returns_masked_questions(client, ctx, db):
    """POST /quizzes/{id}/attempts returns attempt with questions masked."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    setup = _make_published_open_quiz(db, ctx, faculty)
    ctx.make_enrollment(student["student_id"], setup["subject_id"])

    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    h = ctx.headers(token)

    resp = client.post(f"/quizzes/{setup['quiz_id']}/attempts", headers=h)
    assert resp.status_code == 201
    body = resp.json()
    assert body["attempt_number"] == 1
    assert body["attempts_left"] == 1
    assert len(body["questions"]) == 2

    for q in body["questions"]:
        assert "correct_option" not in q
        assert "explanation" not in q
        assert "correct" not in q


def test_resume_returns_stored_answers(client, ctx, db):
    """GET /attempts/{id} shows saved answers and keeps questions masked."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    setup = _make_published_open_quiz(db, ctx, faculty)
    ctx.make_enrollment(student["student_id"], setup["subject_id"])

    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    h = ctx.headers(token)

    attempt_id, q_ids = _start_attempt(client, h, setup["quiz_id"])

    draft = {q_ids[0]: 0, q_ids[1]: 1}
    resp = client.put(f"/attempts/{attempt_id}/answers", headers=h,
                      json={"answers": draft})
    assert resp.status_code == 200
    assert resp.json() == {"saved": True}

    resp2 = client.get(f"/attempts/{attempt_id}", headers=h)
    assert resp2.status_code == 200
    body = resp2.json()
    assert body["status"] == "in_progress"
    assert body["answers"] == draft
    for q in body["questions"]:
        assert "correct_option" not in q
        assert "explanation" not in q


def test_submit_grades_correct_answers(client, ctx, db):
    """POST /attempts/{id}/submit returns total_score and writes student_co_scores."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    setup = _make_published_open_quiz(db, ctx, faculty)
    ctx.make_enrollment(student["student_id"], setup["subject_id"])

    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    h = ctx.headers(token)

    attempt_id, _ = _start_attempt(client, h, setup["quiz_id"])
    correct = {qk: setup["correct"][qk] for qk in setup["question_keys"]}

    resp = _submit(client, h, attempt_id, correct)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_score"] == 2.0
    assert body["max_score"] == 2.0
    assert len(body["co_scores"]) == 2
    for cs in body["co_scores"]:
        assert cs["marks"] == 1.0
        assert cs["max"] == 1.0
        assert cs["percentage"] == 100.0

    # Verify student_co_scores rows in DB
    conn = get_engine().connect()
    try:
        rows = conn.execute(
            text(
                "SELECT co_id, marks_obtained, max_marks, counted "
                "FROM student_co_scores WHERE attempt_id = :aid"
            ),
            {"aid": attempt_id},
        ).mappings().fetchall()
    finally:
        conn.close()
    assert len(rows) == 2


def test_submit_partial_scores(client, ctx, db):
    """Submit with one correct, one wrong → 1/2."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    setup = _make_published_open_quiz(db, ctx, faculty)
    ctx.make_enrollment(student["student_id"], setup["subject_id"])

    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    h = ctx.headers(token)

    attempt_id, q_ids = _start_attempt(client, h, setup["quiz_id"])
    partial = {q_ids[0]: setup["correct"][q_ids[0]]}

    resp = _submit(client, h, attempt_id, partial)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_score"] == 1.0
    assert body["max_score"] == 2.0


def test_review_reveals_correct_and_explanation(client, ctx, db):
    """GET /attempts/{id}/review reveals correct_option and explanation."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    setup = _make_published_open_quiz(db, ctx, faculty)
    ctx.make_enrollment(student["student_id"], setup["subject_id"])

    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    h = ctx.headers(token)

    attempt_id, _ = _start_attempt(client, h, setup["quiz_id"])
    correct = {qk: setup["correct"][qk] for qk in setup["question_keys"]}
    _submit(client, h, attempt_id, correct)

    resp = client.get(f"/attempts/{attempt_id}/review", headers=h)
    assert resp.status_code == 200
    review = resp.json()
    assert len(review) == 2
    for item in review:
        assert "correct" in item
        assert "explanation" in item
        assert "question" in item
        assert "options" in item


def test_both_attempts_allowed_third_refused(client, ctx, db):
    """Student can start 2 attempts; the third is refused with 409."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    setup = _make_published_open_quiz(db, ctx, faculty)
    ctx.make_enrollment(student["student_id"], setup["subject_id"])

    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    h = ctx.headers(token)
    correct = {qk: setup["correct"][qk] for qk in setup["question_keys"]}

    # Attempt 1
    aid1, _ = _start_attempt(client, h, setup["quiz_id"])
    _submit(client, h, aid1, correct)

    # Attempt 2
    aid2, _ = _start_attempt(client, h, setup["quiz_id"])
    _submit(client, h, aid2, correct)

    # Attempt 3 — refused
    resp = client.post(f"/quizzes/{setup['quiz_id']}/attempts", headers=h)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ATTEMPT_LIMIT_REACHED"


def test_start_attempt_closed_quiz(client, ctx, db):
    """POST /quizzes/{id}/attempts on a closed quiz → QUIZ_CLOSED."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    now = _now()
    setup = _make_published_open_quiz(
        db, ctx, faculty,
        opens_at=now - timedelta(hours=2),
        closes_at=now - timedelta(hours=1),
    )
    ctx.make_enrollment(student["student_id"], setup["subject_id"])

    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    h = ctx.headers(token)

    resp = client.post(f"/quizzes/{setup['quiz_id']}/attempts", headers=h)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "QUIZ_CLOSED"


def test_start_attempt_not_open_quiz(client, ctx, db):
    """POST /quizzes/{id}/attempts on a not-yet-open quiz → QUIZ_NOT_OPEN."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    now = _now()
    setup = _make_published_open_quiz(
        db, ctx, faculty,
        opens_at=now + timedelta(hours=1),
        closes_at=now + timedelta(hours=2),
    )
    ctx.make_enrollment(student["student_id"], setup["subject_id"])

    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    h = ctx.headers(token)

    resp = client.post(f"/quizzes/{setup['quiz_id']}/attempts", headers=h)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "QUIZ_NOT_OPEN"


def test_start_attempt_unpublished_quiz(client, ctx, db):
    """POST /quizzes/{id}/attempts on an unpublished quiz → QUIZ_NOT_PUBLISHED."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    setup = _make_published_open_quiz(db, ctx, faculty)
    ctx.make_enrollment(student["student_id"], setup["subject_id"])

    db.execute(text("UPDATE quizzes SET published = false WHERE id = :id"),
               {"id": setup["quiz_id"]})
    db.commit()

    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    h = ctx.headers(token)

    resp = client.post(f"/quizzes/{setup['quiz_id']}/attempts", headers=h)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "QUIZ_NOT_PUBLISHED"


def test_cross_student_access_forbidden(client, ctx, db):
    """Student B cannot read, save, submit, or review student A's attempt."""
    faculty = ctx.make_faculty()
    student_a = ctx.make_student()
    student_b = ctx.make_student()
    setup = _make_published_open_quiz(db, ctx, faculty)
    ctx.make_enrollment(student_a["student_id"], setup["subject_id"])
    ctx.make_enrollment(student_b["student_id"], setup["subject_id"])

    token_a = ctx.login(usn=student_a["usn"], pin=student_a["pin"]).json()["access_token"]
    token_b = ctx.login(usn=student_b["usn"], pin=student_b["pin"]).json()["access_token"]
    h_a = ctx.headers(token_a)
    h_b = ctx.headers(token_b)

    resp = client.post(f"/quizzes/{setup['quiz_id']}/attempts", headers=h_a)
    assert resp.status_code == 201
    attempt_id = resp.json()["attempt_id"]

    checks = [
        ("get", f"/attempts/{attempt_id}", {}),
        ("put", f"/attempts/{attempt_id}/answers", {"json": {"answers": {}}}),
        ("post", f"/attempts/{attempt_id}/submit", {"json": {"answers": {}}}),
        ("get", f"/attempts/{attempt_id}/review", {}),
    ]
    for method, path, kwargs in checks:
        r = client.request(method, path, headers=h_b, **kwargs)
        assert r.status_code == 403, (
            f"{method.upper()} {path} should be 403, got {r.status_code}"
        )
        assert r.json()["error"]["code"] == "FORBIDDEN"


def test_quiz_list_shows_attempts_used_and_left(client, ctx, db):
    """GET /quizzes includes attempts_used and attempts_left for students."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    setup = _make_published_open_quiz(db, ctx, faculty)
    ctx.make_enrollment(student["student_id"], setup["subject_id"])

    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    h = ctx.headers(token)
    correct = {qk: setup["correct"][qk] for qk in setup["question_keys"]}

    # Before any attempt
    resp = client.get("/quizzes", headers=h)
    quiz = next(q for q in resp.json() if q["id"] == setup["quiz_id"])
    assert quiz["attempts_used"] == 0
    assert quiz["attempts_left"] == 2

    # After 1 attempt (start + submit)
    aid1, _ = _start_attempt(client, h, setup["quiz_id"])
    _submit(client, h, aid1, correct)
    resp2 = client.get("/quizzes", headers=h)
    quiz2 = next(q for q in resp2.json() if q["id"] == setup["quiz_id"])
    assert quiz2["attempts_used"] == 1
    assert quiz2["attempts_left"] == 1

    # After 2 attempts (start + submit)
    aid2, _ = _start_attempt(client, h, setup["quiz_id"])
    _submit(client, h, aid2, correct)
    resp3 = client.get("/quizzes", headers=h)
    quiz3 = next(q for q in resp3.json() if q["id"] == setup["quiz_id"])
    assert quiz3["attempts_used"] == 2
    assert quiz3["attempts_left"] == 0
