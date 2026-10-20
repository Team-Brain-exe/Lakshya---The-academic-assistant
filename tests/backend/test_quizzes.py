"""Tests for quiz approval triggers (contract section 7, but tested here
because the QUESTION_NOT_APPROVED error mapping is part of the core backend)."""

from sqlalchemy import text


def test_draft_question_cannot_go_into_quiz(client, ctx):
    """A draft question cannot be added to a quiz — the DB trigger fires and
    the error is mapped to 409 QUESTION_NOT_APPROVED."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    # Create a DRAFT question
    draft = ctx.make_question(mod["module_id"], co["co_id"],
                              faculty_user_id=faculty["user_id"], status="draft")

    # Try to create a quiz that includes the draft question
    resp = client.post("/quizzes", headers=h, json={
        "module_id": mod["module_id"],
        "title": "Quiz with draft",
        "question_ids": [draft["question_id"]],
        "opens_at": "2025-01-01T00:00:00Z",
        "closes_at": "2025-12-31T23:59:59Z",
    })
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "QUESTION_NOT_APPROVED"

    # Verify the quiz was NOT created (rolled back)
    from backend.app.db import get_engine
    conn = get_engine().connect()
    try:
        row = conn.execute(
            text("SELECT COUNT(*) AS c FROM quizzes WHERE title = 'Quiz with draft'")
        ).mappings().fetchone()
    finally:
        conn.close()
    assert row["c"] == 0


def test_approved_question_can_be_published(client, ctx):
    """End-to-end: create questions, approve, create quiz, publish — succeeds."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    # Create an approved question (via API, then approve)
    resp = client.post("/questions", headers=h, json={
        "module_id": mod["module_id"],
        "co_id": co["co_id"],
        "stem": "Approved Q?",
        "options": ["A", "B", "C", "D"],
        "correct_option": 0,
    })
    assert resp.status_code == 201
    qid = resp.json()["id"]

    resp = client.post(f"/questions/{qid}/approve", headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    # Create quiz with the approved question
    resp = client.post("/quizzes", headers=h, json={
        "module_id": mod["module_id"],
        "title": "Published Quiz",
        "question_ids": [qid],
        "opens_at": "2025-01-01T00:00:00Z",
        "closes_at": "2025-12-31T23:59:59Z",
    })
    assert resp.status_code == 201
    quiz_id = resp.json()["id"]

    # Publish the quiz — should succeed
    resp = client.post(f"/quizzes/{quiz_id}/publish", headers=h)
    assert resp.status_code == 200
    assert resp.json()["published"] is True
    assert "event_id" in resp.json()

    # Now try to add a draft question to the published quiz
    draft = ctx.make_question(mod["module_id"], co["co_id"],
                              faculty_user_id=faculty["user_id"], status="draft",
                              stem="Draft Q")
    resp = client.post(f"/quizzes/{quiz_id}/questions", headers=h, json={
        "question_id": draft["question_id"]
    })
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "QUESTION_NOT_APPROVED"


def test_publish_empty_quiz_fails(client, ctx):
    """Publishing a quiz with no questions returns 409."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    resp = client.post("/quizzes", headers=h, json={
        "module_id": mod["module_id"],
        "title": "Empty Quiz",
        "question_ids": [],
        "opens_at": "2025-01-01T00:00:00Z",
        "closes_at": "2025-12-31T23:59:59Z",
    })
    assert resp.status_code == 201
    quiz_id = resp.json()["id"]

    resp = client.post(f"/quizzes/{quiz_id}/publish", headers=h)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "QUESTION_NOT_APPROVED"
