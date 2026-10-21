"""Tests for roster CSV upload (section 4 of the contract)."""
import io
import json
import uuid

from sqlalchemy import text


def _csv_bytes(content: str) -> tuple:
    return ("file", ("roster.csv", io.BytesIO(content.encode("utf-8")), "text/csv"))


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def test_roster_preview_saves_nothing(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    suf = uuid.uuid4().hex[:6].upper()
    usn1 = f"1AT{suf}01"
    usn2 = f"1AT{suf}02"
    csv = f"usn,name,section\n{usn1},Alice A,A\n{usn2},Bob B,A\n"
    resp = client.post(
        f"/subjects/{subj['subject_id']}/roster/preview",
        headers=h,
        files=[_csv_bytes(csv)],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rows"] == 2
    assert len(data["valid"]) == 2
    assert data["bad_rows"] == []
    assert data["duplicates_in_file"] == []
    assert data["already_enrolled"] == []

    # Verify nothing was written to the DB
    from backend.app.db import get_engine
    conn = get_engine().connect()
    try:
        rows = conn.execute(
            text("SELECT COUNT(*) AS c FROM students WHERE usn IN (:u1, :u2)"),
            {"u1": usn1, "u2": usn2},
        ).mappings().fetchone()
    finally:
        conn.close()
    assert rows["c"] == 0


def test_roster_preview_bad_row_and_duplicate(client, ctx):
    """A bad CSV row and a duplicate USN appear in the report."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    suf = uuid.uuid4().hex[:6].upper()
    usn = f"1AT{suf}01"
    csv = (
        "usn,name,section\n"
        f"{usn},Alice A,A\n"           # valid (row 2)
        ",Missing Name,A\n"            # bad: empty usn (row 3)
        f"{usn},Alice Dup,A\n"         # duplicate (row 4)
    )
    resp = client.post(
        f"/subjects/{subj['subject_id']}/roster/preview",
        headers=h,
        files=[_csv_bytes(csv)],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rows"] == 3
    # Only first occurrence of usn is valid
    assert len(data["valid"]) == 1
    assert data["valid"][0]["usn"] == usn
    # The bad row (empty usn) appears in bad_rows
    assert any("missing usn" in br["reason"].lower() for br in data["bad_rows"])
    # The duplicate appears in duplicates_in_file
    assert len(data["duplicates_in_file"]) == 1
    assert data["duplicates_in_file"][0]["usn"] == usn


# ---------------------------------------------------------------------------
# Confirm
# ---------------------------------------------------------------------------

def test_roster_confirm_creates_students_and_credentials(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    suf = uuid.uuid4().hex[:6].upper()
    usn3 = f"1AT{suf}03"
    usn4 = f"1AT{suf}04"
    csv = f"usn,name,section\n{usn3},Carol C,A\n{usn4},Dave D,A\n"
    resp = client.post(
        f"/subjects/{subj['subject_id']}/roster",
        headers=h,
        files=[_csv_bytes(csv)],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created_students"] == 2
    assert data["created_enrollments"] == 2
    assert len(data["credentials"]) == 2

    # Verify PINs are 6 digits
    for cred in data["credentials"]:
        assert len(cred["pin"]) == 6
        assert cred["pin"].isdigit()

    # Register USNs for cleanup (students were created by the roster endpoint)
    for cred in data["credentials"]:
        ctx.register_usn(cred["usn"])

    # Verify the two students can log in with their new PINs
    for cred in data["credentials"]:
        login_resp = client.post("/auth/login", json={"usn": cred["usn"], "pin": cred["pin"]})
        assert login_resp.status_code == 200, f"Login failed for {cred['usn']}"


def test_roster_confirm_again_no_duplicates_no_new_pins(client, ctx):
    """Running roster confirm again creates no duplicates and issues no new PINs."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    suf = uuid.uuid4().hex[:6].upper()
    usn5 = f"1AT{suf}05"
    usn6 = f"1AT{suf}06"
    csv = f"usn,name,section\n{usn5},Eve E,A\n{usn6},Frank F,A\n"

    # First upload
    resp = client.post(
        f"/subjects/{subj['subject_id']}/roster",
        headers=h,
        files=[_csv_bytes(csv)],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created_students"] == 2
    assert data["created_enrollments"] == 2
    first_credentials = {c["usn"]: c["pin"] for c in data["credentials"]}

    # Register USNs for cleanup
    for usn in first_credentials:
        ctx.register_usn(usn)

    # Second upload — same CSV
    resp = client.post(
        f"/subjects/{subj['subject_id']}/roster",
        headers=h,
        files=[_csv_bytes(csv)],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created_students"] == 0
    assert data["created_enrollments"] == 0
    assert data["credentials"] == []

    # Verify PINs haven't changed by logging in with the original PINs
    for usn, pin in first_credentials.items():
        login_resp = client.post("/auth/login", json={"usn": usn, "pin": pin})
        assert login_resp.status_code == 200


def test_roster_existing_student_keeps_pin(client, ctx):
    """An existing student (same USN) is enrolled without changing their PIN."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    # Create a student with a known PIN and a unique USN
    suf = uuid.uuid4().hex[:6].upper()
    usn = f"1AT{suf}00"
    student = ctx.make_student(usn=usn, pin="999999")
    original_pin = student["pin"]

    # Enroll the student via roster with a different PIN provided
    csv = f"usn,name,section,pin\n{usn},Existing Student,A,111111\n"
    resp = client.post(
        f"/subjects/{subj['subject_id']}/roster",
        headers=h,
        files=[_csv_bytes(csv)],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created_students"] == 0
    assert data["created_enrollments"] == 1
    assert data["credentials"] == []  # No credentials for existing student

    # Original PIN still works
    login_resp = client.post("/auth/login", json={"usn": usn, "pin": "999999"})
    assert login_resp.status_code == 200

    # Old provided PIN does NOT work
    login_resp = client.post("/auth/login", json={"usn": usn, "pin": "111111"})
    assert login_resp.status_code == 401


def test_roster_provided_pin_for_new_student(client, ctx):
    """When a PIN is provided in the CSV for a new student, it is used."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    suf = uuid.uuid4().hex[:6].upper()
    usn = f"1AT{suf}00"
    csv = f"usn,name,section,pin\n{usn},Provided Pin,A,424242\n"
    resp = client.post(
        f"/subjects/{subj['subject_id']}/roster",
        headers=h,
        files=[_csv_bytes(csv)],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created_students"] == 1
    assert len(data["credentials"]) == 1
    assert data["credentials"][0]["usn"] == usn
    assert data["credentials"][0]["pin"] == "424242"

    # Register USN for cleanup (student was created by the roster endpoint)
    ctx.register_usn(usn)

    # Verify login with provided PIN works
    login_resp = client.post("/auth/login", json={"usn": usn, "pin": "424242"})
    assert login_resp.status_code == 200


def test_roster_preview_with_invalid_csv(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    # Missing required column "section"
    suf = uuid.uuid4().hex[:6].upper()
    usn = f"1AT{suf}01"
    csv = f"usn,name\n{usn},Alice A\n"
    resp = client.post(
        f"/subjects/{subj['subject_id']}/roster/preview",
        headers=h,
        files=[_csv_bytes(csv)],
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "BAD_REQUEST"
