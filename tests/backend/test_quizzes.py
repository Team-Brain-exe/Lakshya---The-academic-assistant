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


# ---------------------------------------------------------------------------
# GET /quizzes and GET /quizzes/{id}
# ---------------------------------------------------------------------------

def test_list_quizzes_faculty_sees_own(client, ctx):
    """Faculty see all quizzes for their subjects (published and unpublished)."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    # Create two unpublished quizzes
    ctx.make_quiz(mod["module_id"], subj["subject_id"], faculty_user_id=faculty["user_id"], title="Quiz A")
    ctx.make_quiz(mod["module_id"], subj["subject_id"], faculty_user_id=faculty["user_id"], title="Quiz B")

    resp = client.get("/quizzes", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    titles = {q["title"] for q in data}
    assert titles == {"Quiz A", "Quiz B"}


def test_list_quizzes_student_sees_only_published(client, ctx):
    """Students see only published quizzes for subjects they're enrolled in."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    subj = ctx.make_subject(faculty["user_id"])
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")
    co = ctx.make_co(subj["subject_id"], 1, "CO1")

    # Enroll the student
    ctx.make_enrollment(student["student_id"], subj["subject_id"])

    # Approved question so we can create and publish a quiz
    q = ctx.make_question(mod["module_id"], co["co_id"],
                          faculty_user_id=faculty["user_id"], status="approved")

    # Faculty creates two quizzes: one unpublished, one published
    quiz_unpub = ctx.make_quiz(mod["module_id"], subj["subject_id"],
                               faculty_user_id=faculty["user_id"], title="Unpublished")
    quiz_pub = ctx.make_quiz(mod["module_id"], subj["subject_id"],
                             faculty_user_id=faculty["user_id"], title="Published",
                             question_ids=[q["question_id"]])

    # Add the approved question to the first quiz too, then publish it
    client.post(f"/quizzes/{quiz_unpub['quiz_id']}/questions", headers=ctx.headers(
        ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    ), json={"question_id": q["question_id"]})
    client.post(f"/quizzes/{quiz_pub['quiz_id']}/publish", headers=ctx.headers(
        ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    ))

    # Student should only see the published quiz
    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    resp = client.get("/quizzes", headers=ctx.headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Published"
    assert data[0]["published"] is True
    assert data[0]["question_count"] == 1


def test_list_quizzes_student_not_enrolled_sees_empty(client, ctx):
    """A student not enrolled in any subject sees no quizzes."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    subj = ctx.make_subject(faculty["user_id"])
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")
    ctx.make_quiz(mod["module_id"], subj["subject_id"], faculty_user_id=faculty["user_id"])

    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    resp = client.get("/quizzes", headers=ctx.headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_quizzes_with_subject_filter(client, ctx):
    """Faculty can filter quizzes by subject_id."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj_a = ctx.make_subject(faculty["user_id"])
    subj_b = ctx.make_subject(faculty["user_id"], code="OTHER123")
    mod_a = ctx.make_module(subj_a["subject_id"], 1, "Mod A")
    mod_b = ctx.make_module(subj_b["subject_id"], 1, "Mod B")

    ctx.make_quiz(mod_a["module_id"], subj_a["subject_id"], faculty_user_id=faculty["user_id"], title="Q A1")
    ctx.make_quiz(mod_b["module_id"], subj_b["subject_id"], faculty_user_id=faculty["user_id"], title="Q B1")

    resp = client.get(f"/quizzes?subject_id={subj_a['subject_id']}", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Q A1"


def test_get_quiz_by_id_faculty(client, ctx):
    """Faculty can retrieve their own quiz by ID."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    quiz = ctx.make_quiz(mod["module_id"], subj["subject_id"], faculty_user_id=faculty["user_id"])

    resp = client.get(f"/quizzes/{quiz['quiz_id']}", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == quiz["quiz_id"]
    assert data["title"] == quiz["title"]
    assert data["published"] is False


def test_get_quiz_by_id_student_sees_published(client, ctx):
    """Student can see a published quiz for a subject they are enrolled in."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    subj = ctx.make_subject(faculty["user_id"])
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")
    co = ctx.make_co(subj["subject_id"], 1, "CO1")

    ctx.make_enrollment(student["student_id"], subj["subject_id"])

    q = ctx.make_question(mod["module_id"], co["co_id"],
                          faculty_user_id=faculty["user_id"], status="approved")
    quiz = ctx.make_quiz(mod["module_id"], subj["subject_id"],
                         faculty_user_id=faculty["user_id"], question_ids=[q["question_id"]])

    # Faculty publishes the quiz
    ftoken = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    client.post(f"/quizzes/{quiz['quiz_id']}/publish", headers=ctx.headers(ftoken))

    # Student retrieves the published quiz
    stoken = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    resp = client.get(f"/quizzes/{quiz['quiz_id']}", headers=ctx.headers(stoken))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == quiz["quiz_id"]
    assert data["published"] is True
    assert data["question_count"] == 1


def test_get_quiz_student_unpublished_returns_404(client, ctx):
    """Student gets 404 for an unpublished quiz (even if enrolled)."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    subj = ctx.make_subject(faculty["user_id"])
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    ctx.make_enrollment(student["student_id"], subj["subject_id"])
    quiz = ctx.make_quiz(mod["module_id"], subj["subject_id"], faculty_user_id=faculty["user_id"])

    stoken = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    resp = client.get(f"/quizzes/{quiz['quiz_id']}", headers=ctx.headers(stoken))
    assert resp.status_code == 404


def test_get_quiz_not_found(client, ctx):
    """GET /quizzes/{id} for a non-existent quiz returns 404."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    import uuid
    resp = client.get(f"/quizzes/{uuid.uuid4()}", headers=ctx.headers(token))
    assert resp.status_code == 404
