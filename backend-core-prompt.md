You are building the core of the FastAPI backend for this repo. Read these first and treat them as the source of truth:

- docs/api-contract.md (sections 1 to 5 and 13 are yours: conventions, auth, subjects/COs/modules, roster, questions, health)
- backend/migrations/001_init.sql, 002_lock_down_api.sql, 003_user_name.sql (the database schema)
- README.md and .env.example

Do not change the schema or the contract. If you think either has a bug, stop and tell me what and why. Never print, log or commit secrets. Do not run git commit; I will review first.

## Stack

FastAPI, SQLAlchemy 2.0 using Core with `text()` queries (no ORM models needed), psycopg 3, python-dotenv, bcrypt, PyJWT, python-multipart. Tests: pytest and httpx. Put dependencies in backend/requirements.txt.

`DATABASE_URL` in .env starts with `postgresql://`. Convert it to `postgresql+psycopg://` for SQLAlchemy. The database is Supabase Postgres through the session pooler, so use `pool_pre_ping=True` and a small pool.

## Layout

```
backend/app/main.py        app, CORS (FRONTEND_ORIGIN), router includes, exception handlers
backend/app/config.py      settings from env (DATABASE_URL, SESSION_SECRET, FRONTEND_ORIGIN, ATTEMPT_RULE, MAX_ATTEMPTS)
backend/app/db.py          engine and a get_conn dependency (one transaction per request)
backend/app/security.py    bcrypt hash/verify, JWT create/decode (HS256, 8 hour expiry)
backend/app/deps.py        get_current_user, require_faculty, require_student
backend/app/errors.py      AppError class and handlers that produce the contract's error format
backend/app/routers/       auth.py, subjects.py, modules.py, roster.py, questions.py, health.py
backend/scripts/create_faculty.py   CLI: create a faculty user (email, name, password via prompt)
backend/migrations/apply.py         runs every .sql file in backend/migrations/ in name order
tests/backend/             pytest tests
```

Other people will add their routers (upload, quizzes, sheet, agent and so on) under backend/app/routers/. Make main.py include routers in a simple list so adding one is a one-line change. Use the path prefixes from the contract exactly (no /api prefix).

## Rules that must hold

1. The current user comes only from the verified JWT, through `get_current_user()`, which returns `{user_id, role, student_id, usn}`. Never read user, role or USN from a body, query string or header other than Authorization.
2. Every error response uses `{"error": {"code", "message", "details"?}}` with the code and HTTP status from the contract's table. This includes FastAPI validation errors (422 `VALIDATION_ERROR`), 404s, and unexpected exceptions (500 `INTERNAL_ERROR`, no stack trace in the body).
3. Map database errors: unique violation to 409 `CONFLICT`; check violation raised by the approval triggers to 409 `QUESTION_NOT_APPROVED`; other check violations to 422 `VALIDATION_ERROR`.
4. Faculty only touch subjects where `subjects.faculty_user_id` equals their user id. Another faculty's subject returns 404. Students can only call `GET /subjects` and `GET /subjects/{id}`, limited to subjects they are enrolled in. Everything else is faculty only, and a student token gets 403 `FORBIDDEN`.
5. USNs are trimmed and uppercased everywhere before lookup or insert.
6. Login: `POST /auth/login` accepts `{usn, pin}` or `{email, password}`. Wrong credentials give the same 401 message whether the user exists or not. Verify against a dummy hash when the user does not exist so timing does not leak it. Add an in-memory rate limit (for example 5 failures per 15 minutes per USN/email and per IP) that returns 429 `RATE_LIMITED`.
7. Student login finds the `students` row by USN, checks `pin_hash`, then loads the matching `users` row (role student) for the token `sub`. The JWT carries `sub`, `role`, `student_id`, `usn`.
8. Roster: `POST /subjects/{id}/roster/preview` parses the CSV (columns usn, name, section; optional pin) and saves nothing. It returns total_rows, valid, bad_rows (with a reason), duplicates_in_file and already_enrolled. `POST /subjects/{id}/roster` does the same parsing and then, in one transaction, creates new students (random 6-digit PIN with the `secrets` module, bcrypt hashed, plus a `users` row of role student), enrolls them, skips existing enrollments, and returns the created counts and `credentials: [{usn, pin}]` for new students only. Plain PINs are never stored or logged. An existing student keeps their PIN.
9. `PUT /subjects/{id}/cos` upserts by number (1 to 6) in one transaction.
10. Questions: `GET /questions` requires `module_id`; filters co_id, status and source. `POST /questions` creates a faculty-written draft. `POST /questions/batch` saves AI drafts (source AI, status draft). Approve and reject set the status. Validate that the module and CO belong to a subject the caller owns, and that the CO belongs to the module's subject. Include `co_number` in every question response.
11. `GET /health` is public and returns `{"status": "ok"}`.

## Scripts

- `backend/scripts/create_faculty.py`: prompts for email, name and password (use getpass), bcrypt hashes it, inserts into `users` (role faculty). Nobody can log in as faculty without this, so make it work first.
- `backend/migrations/apply.py`: runs each .sql file in order inside its own transaction. The files are safe to re-run.

## Tests (tests/backend/)

Run against the real DATABASE_URL, but have each test create its own rows with unique values (for example a random suffix on USNs and emails) and delete them afterwards. Cover:

- student login works; wrong PIN returns 401; lowercase USN with spaces still logs in
- faculty login works; wrong password returns 401
- six wrong logins in a row return 429
- a request with no token returns 401; a student token on `POST /subjects` returns 403
- a faculty member cannot read another faculty member's subject (404)
- a student cannot read a subject they are not enrolled in
- creating CO7 returns 422; `PUT /subjects/{id}/cos` is idempotent
- roster preview saves nothing; roster confirm creates students and returns credentials once; running it again creates no duplicates and issues no new PINs
- a bad CSV row and a duplicate USN appear in the report
- a draft question cannot go into a published quiz (insert via SQL and expect the trigger error mapped to 409 `QUESTION_NOT_APPROVED`)

## How to finish

1. Make sure `.env` is in .gitignore (it is) and that no test prints a secret.
2. Tell me the exact commands to: install dependencies, apply migrations, create the first faculty user, start the server (`uvicorn backend.app.main:app --reload`), and run the tests.
3. Run the tests and show me the results. Fix failures in the code, not by weakening the tests.
4. List anything in the contract you could not implement exactly, and why.
