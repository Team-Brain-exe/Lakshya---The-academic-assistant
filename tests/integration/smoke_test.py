"""Hosted-app smoke test. Reads credentials from environment/.env and never prints them.

Required variables:
  SMOKE_BASE_URL, SMOKE_FACULTY_EMAIL, SMOKE_FACULTY_PASSWORD, SMOKE_SUBJECT_ID

Run with: python tests/integration/smoke_test.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()


def validate_base_url(value: str) -> str:
    """Refuse plaintext or credential-bearing endpoints before sending login data."""
    try:
        parsed = urlsplit(value.strip())
        has_host = bool(parsed.hostname)
    except ValueError as exc:
        raise RuntimeError("SMOKE_BASE_URL must be a valid HTTPS URL.") from exc
    if parsed.scheme.lower() != "https" or not has_host:
        raise RuntimeError("SMOKE_BASE_URL must be an HTTPS URL before credentials are sent.")
    if parsed.username is not None or parsed.password is not None:
        raise RuntimeError("SMOKE_BASE_URL must not contain embedded credentials.")
    if parsed.query or parsed.fragment:
        raise RuntimeError("SMOKE_BASE_URL must not contain a query or fragment.")
    return value.strip().rstrip("/")


def run_smoke_test() -> None:
    base_url = validate_base_url(_required("SMOKE_BASE_URL"))
    email = _required("SMOKE_FACULTY_EMAIL")
    password = _required("SMOKE_FACULTY_PASSWORD")
    subject_id = _required("SMOKE_SUBJECT_ID")
    scope = os.getenv("SMOKE_EXPORT_SCOPE", "semester")
    module_id = os.getenv("SMOKE_EXPORT_MODULE_ID")

    with httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=False) as client:
        health = client.get("/health")
        health.raise_for_status()
        if health.json().get("status") != "ok":
            raise RuntimeError("Health endpoint did not report ok")
        print("PASS health")

        login = client.post("/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        token = login.json().get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Login response did not include an access token")
        headers = {"Authorization": f"Bearer {token}"}
        print("PASS faculty login")

        agent = client.post(
            "/agent/chat",
            headers=headers,
            json={"message": "Summarize the weakest course outcomes for my subject."},
        )
        agent.raise_for_status()
        agent_body = agent.json()
        if not isinstance(agent_body.get("reply"), str) or not agent_body["reply"].strip():
            raise RuntimeError("Agent chat returned no reply")
        print("PASS agent chat")

        params = {"scope": scope}
        if module_id:
            params["module_id"] = module_id
        export = client.get(f"/subjects/{subject_id}/co-sheet/export", headers=headers, params=params)
        export.raise_for_status()
        if not export.content:
            raise RuntimeError("CO sheet export returned an empty file")
        content_type = export.headers.get("content-type", "").lower()
        if "spreadsheet" not in content_type and "octet-stream" not in content_type:
            raise RuntimeError("CO sheet export did not return a spreadsheet content type")
        print("PASS CO sheet export")


def main() -> int:
    try:
        run_smoke_test()
    except (RuntimeError, httpx.HTTPError) as exc:
        print(f"SMOKE TEST BLOCKED/FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
