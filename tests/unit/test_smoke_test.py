from __future__ import annotations

from pathlib import Path
from runpy import run_path

import pytest


SMOKE = run_path(str(Path(__file__).resolve().parents[1] / "integration" / "smoke_test.py"))
validate_base_url = SMOKE["validate_base_url"]


def test_smoke_base_url_requires_https_before_login_credentials_are_sent():
    with pytest.raises(RuntimeError, match="HTTPS"):
        validate_base_url("http://example.test")


def test_smoke_base_url_rejects_embedded_credentials():
    with pytest.raises(RuntimeError, match="credentials"):
        validate_base_url("https://faculty:password@example.test")


def test_smoke_base_url_accepts_https_and_removes_trailing_slash():
    assert validate_base_url("https://academic.example.test/") == "https://academic.example.test"


def test_smoke_login_does_not_follow_redirect_with_credentials(monkeypatch):
    import httpx

    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/auth/login":
            return httpx.Response(307, headers={"location": "https://attacker.example/collect"})
        return httpx.Response(401)

    real_client = httpx.Client
    transport = httpx.MockTransport(handler)

    def client_factory(**kwargs):
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(SMOKE["httpx"], "Client", client_factory)
    monkeypatch.setenv("SMOKE_BASE_URL", "https://academic.example.test")
    monkeypatch.setenv("SMOKE_FACULTY_EMAIL", "faculty@example.test")
    monkeypatch.setenv("SMOKE_FACULTY_PASSWORD", "sensitive-password")
    monkeypatch.setenv("SMOKE_SUBJECT_ID", "subject-1")

    with pytest.raises(httpx.HTTPStatusError):
        SMOKE["run_smoke_test"]()

    assert [request.url.path for request in requests] == ["/health", "/auth/login"]
    assert requests[1].content == b'{"email":"faculty@example.test","password":"sensitive-password"}'
    assert not any(request.url.host == "attacker.example" for request in requests)
