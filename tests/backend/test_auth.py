"""Tests for auth endpoints (section 2 of the contract)."""


# ---------------------------------------------------------------------------
# Student login
# ---------------------------------------------------------------------------

def test_student_login_success(client, ctx):
    student = ctx.make_student(pin="483920")
    resp = ctx.login(usn=student["usn"], pin="483920")
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["role"] == "student"
    assert data["user"]["id"] is not None
    assert data["user"]["usn"] == student["usn"]
    assert data["user"]["email"] is None
    assert "access_token" in data

    # The returned token should be usable
    headers = ctx.headers(data["access_token"])
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == "student"


def test_student_wrong_pin_returns_401(client, ctx):
    student = ctx.make_student()
    resp = ctx.login(usn=student["usn"], pin="000000")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_student_login_lowercase_usn_with_spaces(client, ctx):
    """USN is trimmed and uppercased by the server before lookup."""
    student = ctx.make_student(usn="1AT0CS042", pin="483920")
    # Send lowercase USN with leading/trailing spaces
    resp = ctx.login(usn="  1at0cs042  ", pin="483920")
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "student"
    assert data["user"]["usn"] == "1AT0CS042"


def test_student_login_nonexistent_user_returns_401(client, ctx):
    """Wrong credentials give the same 401 message whether the user exists or not."""
    resp = ctx.login(usn="NOPE999", pin="000000")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    assert resp.json()["error"]["message"] == "Invalid credentials"


def test_student_login_wrong_pin_same_message(client, ctx):
    """Wrong PIN gives the same 401 message as nonexistent user."""
    student = ctx.make_student()
    resp = ctx.login(usn=student["usn"], pin="000000")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    assert resp.json()["error"]["message"] == "Invalid credentials"


# ---------------------------------------------------------------------------
# Faculty login
# ---------------------------------------------------------------------------

def test_faculty_login_success(client, ctx):
    faculty = ctx.make_faculty()
    resp = ctx.login(email=faculty["email"], password=faculty["password"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["role"] == "faculty"
    assert data["user"]["id"] == faculty["user_id"]
    assert data["user"]["email"] == faculty["email"]
    assert data["user"]["usn"] is None
    assert "access_token" in data


def test_faculty_wrong_password_returns_401(client, ctx):
    faculty = ctx.make_faculty()
    resp = ctx.login(email=faculty["email"], password="wrongpassword")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_login_requires_either_usn_pin_or_email_password(client, ctx):
    resp = client.post("/auth/login", json={})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def test_six_wrong_logins_return_429(client, ctx):
    student = ctx.make_student()
    for i in range(5):
        resp = ctx.login(usn=student["usn"], pin="000000")
        assert resp.status_code == 401, f"Attempt {i+1} should be 401"

    # 6th attempt: rate limited
    resp = ctx.login(usn=student["usn"], pin="000000")
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "RATE_LIMITED"

    # Correct credentials are also blocked while rate-limited
    resp = ctx.login(usn=student["usn"], pin=student["pin"])
    assert resp.status_code == 429


def test_rate_limit_is_per_identifier(client, ctx):
    """Rate limiting one USN should not block a different USN."""
    student1 = ctx.make_student()
    student2 = ctx.make_student()

    # 5 failures for student1
    for _ in range(5):
        ctx.login(usn=student1["usn"], pin="000000")

    # student2 should still be able to log in
    resp = ctx.login(usn=student2["usn"], pin=student2["pin"])
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Token / auth header enforcement
# ---------------------------------------------------------------------------

def test_no_token_returns_401(client, ctx):
    resp = client.post("/subjects", json={"code": "X", "name": "Y", "semester": 1})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_student_token_on_faculty_endpoint_returns_403(client, ctx):
    student = ctx.make_student()
    resp = ctx.login(usn=student["usn"], pin=student["pin"])
    token = resp.json()["access_token"]
    headers = ctx.headers(token)

    resp = client.post("/subjects", headers=headers,
                       json={"code": "X", "name": "Y", "semester": 1})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_expired_or_invalid_token_returns_401(client, ctx):
    headers = {"Authorization": "Bearer garbage.token.here"}
    resp = client.get("/subjects", headers=headers)
    assert resp.status_code == 401
