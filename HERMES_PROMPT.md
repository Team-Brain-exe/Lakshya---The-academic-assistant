Read backend/migrations/001_init.sql. Do not change the schema unless you find a real bug, and tell me if you do.

Create two things:

1. backend/migrations/apply.py: loads DATABASE_URL from .env (python-dotenv), connects with psycopg 3, and runs every .sql file in backend/migrations/ in name order, in one transaction.

2. tests/db/test_constraints.py using pytest and psycopg. Connect to DATABASE_URL, run every test inside a transaction that is rolled back at the end, and keep the test data small. Each test must prove the database rejects the bad insert (expect a psycopg.errors.CheckViolation, UniqueViolation or similar):
 - a third attempt (attempt_number = 3) and attempt_number = 0
 - the same student, quiz and attempt_number inserted twice
 - a duplicate students.usn
 - a duplicate enrollment for the same student and subject
 - a draft question added to quiz_questions
 - publishing a quiz that contains an unapproved question, and publishing a quiz with no questions
 - un-approving a question that is in a published quiz
 - course_outcomes.number = 7
 - a question with 3 options
 Also add one happy-path test: an approved question can be added and the quiz can be published.

Never print or commit secrets. Make sure .env is in .gitignore. Add psycopg[binary], python-dotenv and pytest to backend/requirements.txt. Do not git commit anything; I will review first.
