"""Tests that verify DB-level constraints and triggers reject invalid data.

Each test uses raw SQL (via the ctx fixture's live connection) to attempt a
violation and asserts the database rejects it.  Prerequisite rows are created
through the ctx fixture (tracked for cleanup); any intermediate valid rows
created mid-test are removed in a finally block.
"""
import pytest
from sqlalchemy import text, exc


# ---------------------------------------------------------------------------
# 1. Quiz attempt_number CHECK — value outside 1-2
# ---------------------------------------------------------------------------
def test_quiz_attempt_number_outside_1_2(db, ctx):
    """CHECK (attempt_number IN (1, 2)) rejects attempt_number = 5."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    subject = ctx.make_subject(faculty["user_id"])
    quiz = ctx.make_quiz(None, subject["subject_id"],
                         faculty_user_id=faculty["user_id"])

    try:
        with pytest.raises(exc.IntegrityError):
            db.execute(text(
                "INSERT INTO quiz_attempts "
                "(quiz_id, student_id, attempt_number, answers) "
                "VALUES (:qid, :sid, 5, '{}')"
            ), {"qid": quiz["quiz_id"], "sid": student["student_id"]})
            db.commit()
    finally:
        db.rollback()


# ---------------------------------------------------------------------------
# 2. A third attempt (same student + quiz) — UNIQUE violation
# ---------------------------------------------------------------------------
def test_quiz_third_attempt_unique_violation(db, ctx):
    """UNIQUE (student_id, quiz_id, attempt_number) rejects a duplicate
    (student, quiz, attempt_number) pair — simulating a 'third attempt' by
    re-using attempt_number 1."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    subject = ctx.make_subject(faculty["user_id"])
    quiz = ctx.make_quiz(None, subject["subject_id"],
                         faculty_user_id=faculty["user_id"])

    attempt_ids = []
    try:
        # First attempt — succeeds
        r = db.execute(text(
            "INSERT INTO quiz_attempts "
            "(quiz_id, student_id, attempt_number, answers) "
            "VALUES (:qid, :sid, 1, '{}') RETURNING id"
        ), {"qid": quiz["quiz_id"], "sid": student["student_id"]})
        attempt_ids.append(str(r.mappings().fetchone()["id"]))

        # Second attempt — succeeds
        r = db.execute(text(
            "INSERT INTO quiz_attempts "
            "(quiz_id, student_id, attempt_number, answers) "
            "VALUES (:qid, :sid, 2, '{}') RETURNING id"
        ), {"qid": quiz["quiz_id"], "sid": student["student_id"]})
        attempt_ids.append(str(r.mappings().fetchone()["id"]))

        db.commit()

        # Third insert with attempt_number=1 (duplicate) → UNIQUE violation
        with pytest.raises(exc.IntegrityError):
            db.execute(text(
                "INSERT INTO quiz_attempts "
                "(quiz_id, student_id, attempt_number, answers) "
                "VALUES (:qid, :sid, 1, '{}')"
            ), {"qid": quiz["quiz_id"], "sid": student["student_id"]})
            db.commit()
    finally:
        db.rollback()
        # Clean up valid attempts created mid-test
        for aid in attempt_ids:
            try:
                db.execute(text("DELETE FROM quiz_attempts WHERE id = :id"),
                           {"id": aid})
            except Exception:
                pass
        db.commit()


# ---------------------------------------------------------------------------
# 3. Duplicate USN (students.usn UNIQUE)
# ---------------------------------------------------------------------------
def test_duplicate_usn(db, ctx):
    """students.usn has a UNIQUE constraint — inserting a duplicate USN
    must be rejected."""
    student = ctx.make_student()

    try:
        with pytest.raises(exc.IntegrityError):
            db.execute(text(
                "INSERT INTO students (usn, name, pin_hash) "
                "VALUES (:usn, :name, :hash)"
            ), {"usn": student["usn"],
                "name": "Dup Name",
                "hash": "dummy_hash"})
            db.commit()
    finally:
        db.rollback()


# ---------------------------------------------------------------------------
# 4. Duplicate (student_id, subject_id) enrollment
# ---------------------------------------------------------------------------
def test_duplicate_enrollment(db, ctx):
    """UNIQUE (student_id, subject_id) on enrollments rejects a second
    enrollment for the same student+subject pair."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    subject = ctx.make_subject(faculty["user_id"])

    # First enrollment via ctx factory — succeeds
    ctx.make_enrollment(student["student_id"], subject["subject_id"])

    try:
        # Second enrollment with same (student_id, subject_id) via raw SQL
        with pytest.raises(exc.IntegrityError):
            db.execute(text(
                "INSERT INTO enrollments (student_id, subject_id, section) "
                "VALUES (:sid, :subj, :sec)"
            ), {"sid": student["student_id"],
                "subj": subject["subject_id"],
                "sec": "B"})
            db.commit()
    finally:
        db.rollback()


# ---------------------------------------------------------------------------
# 5. Adding an unapproved (draft) question to a quiz — trigger
# ---------------------------------------------------------------------------
def test_unapproved_question_cannot_be_added_to_quiz(db, ctx):
    """Trigger fn_quiz_question_must_be_approved rejects inserting a draft
    question into quiz_questions."""
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    subject = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subject["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subject["subject_id"], 1, "Module 1")
    quiz = ctx.make_quiz(mod["module_id"], subject["subject_id"],
                         faculty_user_id=faculty["user_id"])
    # Create a DRAFT (unapproved) question
    draft_q = ctx.make_question(mod["module_id"], co["co_id"],
                                faculty_user_id=faculty["user_id"],
                                status="draft")

    try:
        with pytest.raises(exc.IntegrityError):
            db.execute(text(
                "INSERT INTO quiz_questions (quiz_id, question_id, position) "
                "VALUES (:qid, :qid2, 0)"
            ), {"qid": quiz["quiz_id"], "qid2": draft_q["question_id"]})
            db.commit()
    finally:
        db.rollback()


# ---------------------------------------------------------------------------
# 6. Publishing a quiz that contains an unapproved question — trigger
# ---------------------------------------------------------------------------
def test_publish_quiz_with_unapproved_question(db, ctx):
    """Trigger fn_quiz_publish_check rejects publishing a quiz whose
    questions include an unapproved one.

    Setup: create an *approved* question, add it to a quiz (passes trigger),
    then downgrade its status to 'draft' (allowed — the quiz is not yet
    published).  Publishing the quiz must now fail.
    """
    faculty = ctx.make_faculty()
    student = ctx.make_student()
    subject = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subject["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subject["subject_id"], 1, "Module 1")
    quiz = ctx.make_quiz(mod["module_id"], subject["subject_id"],
                         faculty_user_id=faculty["user_id"])
    # Create an APPROVED question
    q = ctx.make_question(mod["module_id"], co["co_id"],
                          faculty_user_id=faculty["user_id"],
                          status="approved")

    try:
        # Add the approved question to the quiz (passes trigger)
        db.execute(text(
            "INSERT INTO quiz_questions (quiz_id, question_id, position) "
            "VALUES (:qid, :qid2, 0)"
        ), {"qid": quiz["quiz_id"], "qid2": q["question_id"]})
        db.commit()

        # Downgrade the question to 'draft' (quiz not published yet,
        # so fn_question_unapprove_guard does NOT fire)
        db.execute(text(
            "UPDATE questions SET status = 'draft' WHERE id = :id"
        ), {"id": q["question_id"]})
        db.commit()

        # Try to publish the quiz → trigger rejects (unapproved question present)
        with pytest.raises(exc.IntegrityError):
            db.execute(text(
                "UPDATE quizzes SET published = true, published_at = now() "
                "WHERE id = :id"
            ), {"id": quiz["quiz_id"]})
            db.commit()
    finally:
        db.rollback()
        # Restore the question to 'approved' so ctx teardown can delete it
        # (fn_question_unapprove_guard prevents deletion of a question that is
        #  in a published quiz, but the quiz was never published, so this is
        #  only needed if the test partially succeeded)
        try:
            db.execute(text(
                "UPDATE questions SET status = 'approved' WHERE id = :id"
            ), {"id": q["question_id"]})
            db.commit()
        except Exception:
            db.rollback()
