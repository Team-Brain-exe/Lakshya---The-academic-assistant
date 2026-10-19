"""Tests for subjects, COs and modules (section 3 of the contract)."""


# ---------------------------------------------------------------------------
# Subject CRUD
# ---------------------------------------------------------------------------

def test_faculty_create_and_list_subjects(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)

    resp = client.post("/subjects", headers=h, json={
        "code": "CSE101", "name": "Test Subject", "semester": 3,
    })
    assert resp.status_code == 201
    subj = resp.json()
    assert subj["code"] == "CSE101"
    assert subj["name"] == "Test Subject"
    assert subj["semester"] == 3
    assert subj["faculty_user_id"] == faculty["user_id"]
    assert subj["target_attainment_pct"] == 60.0
    assert subj["default_threshold_pct"] == 60.0

    # List
    resp = client.get("/subjects", headers=h)
    assert resp.status_code == 200
    subjects = resp.json()
    assert len(subjects) >= 1
    assert any(s["id"] == subj["id"] for s in subjects)


def test_get_subject_returns_cos_and_modules(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    ctx.make_module(subj["subject_id"], 1, "Module 1")

    resp = client.get(f"/subjects/{subj['subject_id']}", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == subj["subject_id"]
    assert len(data["cos"]) == 1
    assert data["cos"][0]["number"] == 1
    assert len(data["modules"]) == 1
    assert data["modules"][0]["number"] == 1


def test_patch_and_delete_subject(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    # Patch
    resp = client.patch(f"/subjects/{subj['subject_id']}", headers=h,
                        json={"name": "Updated Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"

    # Delete
    resp = client.delete(f"/subjects/{subj['subject_id']}", headers=h)
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}

    # Verify gone
    resp = client.get(f"/subjects/{subj['subject_id']}", headers=h)
    assert resp.status_code == 404


def test_faculty_cannot_read_another_faculty_subject(client, ctx):
    """A faculty member cannot read another faculty member's subject (404)."""
    faculty_a = ctx.make_faculty()
    faculty_b = ctx.make_faculty()
    subj = ctx.make_subject(faculty_a["user_id"])

    token_b = ctx.login(email=faculty_b["email"], password=faculty_b["password"]).json()["access_token"]
    h_b = ctx.headers(token_b)

    resp = client.get(f"/subjects/{subj['subject_id']}", headers=h_b)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_student_cannot_read_subject_not_enrolled_in(client, ctx):
    """A student gets 404 for a subject they are not enrolled in."""
    faculty = ctx.make_faculty()
    subj = ctx.make_subject(faculty["user_id"])
    student = ctx.make_student()
    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    h = ctx.headers(token)

    resp = client.get(f"/subjects/{subj['subject_id']}", headers=h)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_student_can_read_enrolled_subject(client, ctx):
    """A student CAN read a subject they are enrolled in."""
    faculty = ctx.make_faculty()
    subj = ctx.make_subject(faculty["user_id"])
    student = ctx.make_student()
    ctx.make_enrollment(student["student_id"], subj["subject_id"])

    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    h = ctx.headers(token)

    resp = client.get(f"/subjects/{subj['subject_id']}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["id"] == subj["subject_id"]


def test_student_can_list_enrolled_subjects(client, ctx):
    """A student sees only subjects they are enrolled in."""
    faculty = ctx.make_faculty()
    subj1 = ctx.make_subject(faculty["user_id"], code="SUB001")
    subj2 = ctx.make_subject(faculty["user_id"], code="SUB002")
    student = ctx.make_student()
    ctx.make_enrollment(student["student_id"], subj1["subject_id"])

    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    h = ctx.headers(token)

    resp = client.get("/subjects", headers=h)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert subj1["subject_id"] in ids
    assert subj2["subject_id"] not in ids


# ---------------------------------------------------------------------------
# COs
# ---------------------------------------------------------------------------

def test_put_cos_creates_and_updates(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    resp = client.put(f"/subjects/{subj['subject_id']}/cos", headers=h, json={
        "cos": [
            {"number": 1, "description": "CO1"},
            {"number": 2, "description": "CO2", "threshold_pct": 70},
        ]
    })
    assert resp.status_code == 200
    cos = resp.json()
    assert len(cos) == 2
    assert cos[0]["number"] == 1
    assert cos[0]["description"] == "CO1"
    assert cos[1]["threshold_pct"] == 70

    # GET /cos
    resp = client.get(f"/subjects/{subj['subject_id']}/cos", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_put_cos_number_7_returns_422(client, ctx):
    """Creating CO number 7 returns 422 (CHECK constraint 1..6)."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    resp = client.put(f"/subjects/{subj['subject_id']}/cos", headers=h, json={
        "cos": [{"number": 7, "description": "CO7"}]
    })
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_put_cos_idempotent(client, ctx):
    """PUT /subjects/{id}/cos is idempotent — running it again updates, not duplicates."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    body = {"cos": [
        {"number": 1, "description": "CO1"},
        {"number": 2, "description": "CO2"},
    ]}

    resp1 = client.put(f"/subjects/{subj['subject_id']}/cos", headers=h, json=body)
    assert resp1.status_code == 200
    assert len(resp1.json()) == 2

    # Run again
    resp2 = client.put(f"/subjects/{subj['subject_id']}/cos", headers=h, json=body)
    assert resp2.status_code == 200
    assert len(resp2.json()) == 2

    # Verify only 2 COs in DB
    resp3 = client.get(f"/subjects/{subj['subject_id']}/cos", headers=h)
    assert resp3.status_code == 200
    assert len(resp3.json()) == 2


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------

def test_create_list_patch_delete_module(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    # Create
    resp = client.post(f"/subjects/{subj['subject_id']}/modules", headers=h, json={
        "number": 1, "title": "Intro"
    })
    assert resp.status_code == 201
    mod = resp.json()
    assert mod["number"] == 1
    assert mod["title"] == "Intro"
    assert mod["processing_status"] == "pending"

    # Patch
    resp = client.patch(f"/modules/{mod['id']}", headers=h, json={"title": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated"

    # Delete
    resp = client.delete(f"/modules/{mod['id']}", headers=h)
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}


def test_student_cannot_create_module(client, ctx):
    faculty = ctx.make_faculty()
    subj = ctx.make_subject(faculty["user_id"])
    student = ctx.make_student()
    ctx.make_enrollment(student["student_id"], subj["subject_id"])
    token = ctx.login(usn=student["usn"], pin=student["pin"]).json()["access_token"]
    h = ctx.headers(token)

    resp = client.post(f"/subjects/{subj['subject_id']}/modules", headers=h,
                       json={"number": 1, "title": "Intro"})
    assert resp.status_code == 403
