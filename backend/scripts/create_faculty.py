"""Create a faculty user — safe, idempotent wrapper.

Usage:
    python backend/scripts/create_faculty.py

Prompts for email, name and password (password is hidden via getpass).
Uses the project's existing hash_password() and connects to the same
DATABASE_URL that the Render backend uses (loaded from .env at project root).

Safety:
    - Checks if the account already exists before creating.
    - If the account exists, reports it and exits WITHOUT modifying it.
    - Never displays passwords, hashes, or the database URL.
    - Never changes authentication logic.
"""
import os
import sys

# Allow running both as a module and as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import getpass

from sqlalchemy import text

from backend.app.config import DATABASE_URL  # noqa: F401 — ensures .env is loaded
from backend.app.db import get_engine
from backend.app.security import hash_password


def main():
    email = input("Email: ").strip().lower()
    if not email:
        print("Email is required.")
        sys.exit(1)

    engine = get_engine()
    with engine.connect() as conn:
        # ── Check existence WITHOUT exposing any password/hash fields ──
        existing = conn.execute(
            text("SELECT 1 FROM users WHERE email = :e"),
            {"e": email},
        ).fetchone()

        if existing is not None:
            row = conn.execute(
                text("SELECT role FROM users WHERE email = :e"),
                {"e": email},
            ).fetchone()
            print(f"Account already exists for '{email}' (role={row[0] if row else 'unknown'}).")
            print("Not overwriting — use a different email or reset manually in the database.")
            sys.exit(0)

        name = input("Name: ").strip()
        if not name:
            print("Name is required.")
            sys.exit(1)

        password = getpass.getpass("Password (hidden): ")
        if len(password) < 6:
            print("Password must be at least 6 characters.")
            sys.exit(1)

        confirm = getpass.getpass("Confirm password (hidden): ")
        if password != confirm:
            print("Passwords do not match.")
            sys.exit(1)

        password_hash = hash_password(password)
        conn.execute(
            text(
                "INSERT INTO users (role, email, name, password_hash) "
                "VALUES ('faculty', :email, :name, :hash)"
            ),
            {"email": email, "name": name, "hash": password_hash},
        )
        conn.commit()

    print(f"Faculty user '{email}' created successfully.")


if __name__ == "__main__":
    main()
