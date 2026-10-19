"""Tests for questions endpoints (section 5 of the contract)."""
import json


def test_create_question_includes_co_number(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    resp = client.post("/questions", headers=h, json={
        "module_id": mod["module_id"],
        "co_id": co["co_id"],
        "stem": "What is 2+2?",
        "options": ["2", "3", "4", "5"],
        "correct_option": 2,
    })
    assert resp.status_code == 201
    q = resp.json()
    assert q["status"] == "draft"
    assert q["source"] == "faculty"
    assert q["co_number"] == 1
    assert q["options"] == ["2", "3", "4", "5"]
    assert q["correct_option"] == 2
    assert q["created_by"] == faculty["user_id"]


def test_list_questions_by_module(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    ctx.make_question(mod["module_id"], co["co_id"], faculty_user_id=faculty["user_id"],
                      status="draft", stem="Q draft")
    ctx.make_question(mod["module_id"], co["co_id"], faculty_user_id=faculty["user_id"],
                      status="approved", stem="Q approved")

    resp = client.get(f"/questions?module_id={mod['module_id']}", headers=h)
    assert resp.status_code == 200
    qs = resp.json()
    assert len(qs) == 2
    for q in qs:
        assert q["co_number"] == 1

    # Filter by status
    resp = client.get(f"/questions?module_id={mod['module_id']}&status=approved", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_questions_requires_module_id(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)

    resp = client.get("/questions", headers=h)
    assert resp.status_code == 422


def test_approve_and_reject_question(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")
    q = ctx.make_question(mod["module_id"], co["co_id"], faculty_user_id=faculty["user_id"])

    # Approve
    resp = client.post(f"/questions/{q['question_id']}/approve", headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    # Reject
    resp = client.post(f"/questions/{q['question_id']}/reject", headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_batch_creates_ai_drafts(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    resp = client.post("/questions/batch", headers=h, json={
        "questions": [
            {
                "module_id": mod["module_id"],
                "co_id": co["co_id"],
                "stem": "Batch Q1?",
                "options": ["A", "B", "C", "D"],
                "correct_option": 0,
                "source": "AI",
            },
            {
                "module_id": mod["module_id"],
                "co_id": co["co_id"],
                "stem": "Batch Q2?",
                "options": ["A", "B", "C", "D"],
                "correct_option": 1,
                "source": "AI",
            },
        ]
    })
    assert resp.status_code == 201
    qs = resp.json()
    assert len(qs) == 2
    for q in qs:
        assert q["source"] == "AI"
        assert q["status"] == "draft"
        assert q["co_number"] == 1


def test_faculty_cannot_create_question_for_others_module(client, ctx):
    faculty_a = ctx.make_faculty()
    faculty_b = ctx.make_faculty()
    subj = ctx.make_subject(faculty_b["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    token = ctx.login(email=faculty_a["email"], password=faculty_a["password"]).json()["access_token"]
    h = ctx.headers(token)

    resp = client.post("/questions", headers=h, json={
        "module_id": mod["module_id"],
        "co_id": co["co_id"],
        "stem": "Cannot create",
        "options": ["A", "B", "C", "D"],
        "correct_option": 0,
    })
    assert resp.status_code == 404


def test_patch_question(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")
    q = ctx.make_question(mod["module_id"], co["co_id"], faculty_user_id=faculty["user_id"])

    resp = client.patch(f"/questions/{q['question_id']}", headers=h,
                        json={"stem": "Updated stem", "difficulty": "hard"})
    assert resp.status_code == 200
    assert resp.json()["stem"] == "Updated stem"
    assert resp.json()["difficulty"] == "hard"
