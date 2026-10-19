"""Tests for roster CSV upload (section 4 of the contract)."""
import io
import json

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

    csv = "usn,name,section\n1AT0CS001,Alice A,A\n1AT0CS002,Bob B,A\n"
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
            text("SELECT COUNT(*) AS c FROM students WHERE usn IN ('1AT0CS001','1AT0CS002')")
        ).fetchone()
    finally:
        conn.close()
    assert rows["c"] == 0


def test_roster_preview_bad_row_and_duplicate(client, ctx):
    """A bad CSV row and a duplicate USN appear in the report."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    csv = (
        "usn,name,section\n"
        "1AT0CS001,Alice A,A\n"      # valid (row 2)
        ",Missing Name,A\n"          # bad: empty usn (row 3)
        "1AT0CS001,Alice Dup,A\n"    # duplicate (row 4)
    )
    resp = client.post(
        f"/subjects/{subj['subject_id']}/roster/preview",
        headers=h,
        files=[_csv_bytes(csv)],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rows"] == 3
    # Only first occurrence of 1AT0CS001 is valid
    assert len(data["valid"]) == 1
    assert data["valid"][0]["usn"] == "1AT0CS001"
    # The bad row (empty usn) appears in bad_rows
    assert any("missing usn" in br["reason"].lower() for br in data["bad_rows"])
    # The duplicate appears in duplicates_in_file
    assert len(data["duplicates_in_file"]) == 1
    assert data["duplicates_in_file"][0]["usn"] == "1AT0CS001"


# ---------------------------------------------------------------------------
# Confirm
# ---------------------------------------------------------------------------

def test_roster_confirm_creates_students_and_credentials(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    csv = "usn,name,section\n1AT0CS003,Carol C,A\n1AT0CS004,Dave D,A\n"
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

    csv = "usn,name,section\n1AT0CS005,Eve E,A\n1AT0CS006,Frank F,A\n"

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

    # Create a student with a known PIN
    student = ctx.make_student(usn="1AT0CS100", pin="999999")
    original_pin = student["pin"]

    # Enroll the student via roster with a different PIN provided
    csv = "usn,name,section,pin\n1AT0CS100,Existing Student,A,111111\n"
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
    login_resp = client.post("/auth/login", json={"usn": "1AT0CS100", "pin": "999999"})
    assert login_resp.status_code == 200

    # Old provided PIN does NOT work
    login_resp = client.post("/auth/login", json={"usn": "1AT0CS100", "pin": "111111"})
    assert login_resp.status_code == 401


def test_roster_provided_pin_for_new_student(client, ctx):
    """When a PIN is provided in the CSV for a new student, it is used."""
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    csv = "usn,name,section,pin\n1AT0CS200,Provided Pin,A,424242\n"
    resp = client.post(
        f"/subjects/{subj['subject_id']}/roster",
        headers=h,
        files=[_csv_bytes(csv)],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created_students"] == 1
    assert len(data["credentials"]) == 1
    assert data["credentials"][0]["usn"] == "1AT0CS200"
    assert data["credentials"][0]["pin"] == "424242"

    # Verify login with provided PIN works
    login_resp = client.post("/auth/login", json={"usn": "1AT0CS200", "pin": "424242"})
    assert login_resp.status_code == 200


def test_roster_preview_with_invalid_csv(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])

    # Missing required column "section"
    csv = "usn,name\n1AT0CS001,Alice A\n"
    resp = client.post(
        f"/subjects/{subj['subject_id']}/roster/preview",
        headers=h,
        files=[_csv_bytes(csv)],
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "BAD_REQUEST"
