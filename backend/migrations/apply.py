"""Apply all migration .sql files in backend/migrations/ in name order.

Each file runs in its own transaction.  Files are safe to re-run.

Usage:
    python -m backend.migrations.apply
    python backend/migrations/apply.py
"""
import os
import sys

# Allow running both as a module and as a script
_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_dir))
sys.path.insert(0, _project_root)

from sqlalchemy import text

from backend.app.db import get_engine


def apply_migrations():
    engine = get_engine()
    migration_files = sorted(
        f for f in os.listdir(_dir)
        if f.endswith(".sql")
    )

    if not migration_files:
        print("No .sql migration files found.")
        return

    for filename in migration_files:
        filepath = os.path.join(_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            sql = f.read()

        with engine.begin() as conn:
            conn.execute(text(sql))

        print(f"  Applied: {filename}")

    print(f"\nDone. {len(migration_files)} migration(s) applied.")


if __name__ == "__main__":
    apply_migrations()
