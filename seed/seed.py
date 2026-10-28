"""Load the synthetic demo data into the database in DATABASE_URL.

    python -m seed.seed --yes            # load (safe to run twice: rows have fixed ids)
    python -m seed.seed --remove --yes   # delete ONLY the rows this script created

Everything is invented: fake names, fake USNs (1XX23CS001..060), no real students.

What this runner fixes compared with printing seed_data.generate_sql():
  * The database refuses a published quiz that has no approved questions yet, so
    quizzes are inserted as drafts, their questions are linked, and only then published.
  * The generator's password hashes are placeholders that never verify. Real bcrypt
    hashes are created here, so the demo logins work.
  * It also adds the calendar events for the published quizzes and the flashcards and
    notes for each module (built from the slide text, no AI call needed).

It never deletes anything it did not create, and never truncates tables.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

import bcrypt  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from seed.seed_data import (  # noqa: E402
    SYNTHETIC_PASSWORD_HASH,
    SYNTHETIC_PIN_HASH,
    SeedData,
    generate_seed_data,
    generate_sql,
)

DEMO_FACULTY_PASSWORD = "Demo@12345"
DEMO_STUDENT_PIN = "123456"


def _hash(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()


def _database_url() -> str:
    load_dotenv(os.path.join(ROOT, ".env"))
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        sys.exit("DATABASE_URL is not set. Put it in .env (never commit it).")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _describe(url: str) -> str:
    parts = urlsplit(url.replace("postgresql+psycopg", "postgresql", 1))
    return f"{parts.hostname}:{parts.port or 5432}{parts.path}"  # no user or password


def build_sql(seed: SeedData) -> str:
    """The generator's SQL with the two fixes applied."""
    published = [q for q in seed.quizzes if q["published"]]
    drafts = [dict(q, published=False, published_at=None) for q in seed.quizzes]
    sql = generate_sql(dataclasses.replace(seed, quizzes=drafts))

    sql = sql.replace(SYNTHETIC_PIN_HASH, _hash(DEMO_STUDENT_PIN))
    sql = sql.replace(SYNTHETIC_PASSWORD_HASH, _hash(DEMO_FACULTY_PASSWORD))

    after = ["-- Publish only now that every quiz has its approved questions"]
    for q in published:
        after.append(
            f"UPDATE quizzes SET published = TRUE, published_at = '{q['published_at']}' "
            f"WHERE id = '{q['id']}';"
        )
        after.append(
            "INSERT INTO events (subject_id, type, title, starts_at, ends_at, quiz_id, created_by) "
            f"SELECT '{q['subject_id']}', 'quiz', '{q['title'].replace(chr(39), chr(39) * 2)}', "
            f"'{q['opens_at']}', '{q['closes_at']}', '{q['id']}', '{q['created_by']}' "
            f"WHERE NOT EXISTS (SELECT 1 FROM events WHERE quiz_id = '{q['id']}');"
        )
    head, _, _ = sql.rpartition("COMMIT;")
    return head + "\n".join(after) + "\nCOMMIT;\n"


def load(engine) -> None:
    seed = generate_seed_data()
    sql = build_sql(seed)
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur:
            cur.execute(sql)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()

    # Flashcards and notes from slide text, once per module.
    from app.pg.chunks import module_chunks_with_co
    from app.pg.study import PostgresStudyMaterialStore
    from app.services.study_material import generate_module_study_material

    with engine.begin() as conn:
        store = PostgresStudyMaterialStore(conn)
        for m in seed.modules:
            chunks = module_chunks_with_co(conn, m["id"])
            if chunks:
                generate_module_study_material(store, m["id"], m["title"], chunks)

    print(f"Loaded: {len(seed.students)} students, {len(seed.questions)} questions, "
          f"{len(seed.quizzes)} quizzes, {len(seed.quiz_attempts)} attempts.")
    print()
    print("Demo logins (invented):")
    print(f"  Faculty : {seed.faculty_user['email']} / {DEMO_FACULTY_PASSWORD}")
    print(f"  Student : {seed.students[0]['usn']} / {DEMO_STUDENT_PIN}   (all students use this PIN)")
    print(f"  Weak in CO3: the last ~26 students (Section B), e.g. {seed.students[-1]['usn']}")


def remove(engine) -> None:
    """Delete only the rows created by load(), found through their fixed ids."""
    seed = generate_seed_data()
    subject_id = seed.subject["id"]
    student_ids = [s["id"] for s in seed.students]
    with engine.begin() as conn:
        # Quizzes first: quiz_questions protects questions from deletion.
        conn.execute(text("DELETE FROM quizzes WHERE subject_id = :s"), {"s": subject_id})
        conn.execute(text("DELETE FROM subjects WHERE id = :s"), {"s": subject_id})
        conn.execute(text("DELETE FROM students WHERE id = ANY(CAST(:ids AS uuid[]))"),
                     {"ids": "{" + ",".join(student_ids) + "}"})
        conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": seed.faculty_user["id"]})
    print("Removed the seed subject, its students and the seed faculty user.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--remove", action="store_true", help="delete only the rows this script created")
    ap.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    args = ap.parse_args()

    url = _database_url()
    action = "REMOVE the seed data from" if args.remove else "LOAD the seed data into"
    print(f"About to {action}: {_describe(url)}")
    if not args.yes and input("Type 'yes' to continue: ").strip().lower() != "yes":
        sys.exit("Cancelled.")

    engine = create_engine(url, pool_pre_ping=True)
    (remove if args.remove else load)(engine)


if __name__ == "__main__":
    main()
