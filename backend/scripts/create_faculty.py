"""Create a faculty user.

Usage:  python -m backend.scripts.create_faculty
        python backend/scripts/create_faculty.py

Prompts for email, name and password (password is hidden via getpass).
Stores a bcrypt hash in the users table with role = 'faculty'.
"""
import os
import sys

# Allow running both as a module and as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import getpass

from sqlalchemy import text

from backend.app.config import DATABASE_URL
from backend.app.db import get_engine
from backend.app.security import hash_password


def main():
    email = input("Email: ").strip().lower()
    if not email:
        print("Email is required.")
        sys.exit(1)

    name = input("Name: ").strip()
    if not name:
        print("Name is required.")
        sys.exit(1)

    password = getpass.getpass("Password: ")
    if len(password) < 6:
        print("Password must be at least 6 characters.")
        sys.exit(1)

    password_hash = hash_password(password)

    engine = get_engine()
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text(
                    "INSERT INTO users (role, email, name, password_hash) "
                    "VALUES ('faculty', :email, :name, :hash)"
                ),
                {"email": email, "name": name, "hash": password_hash},
            )
    print(f"Faculty user '{email}' created successfully.")


if __name__ == "__main__":
    main()
