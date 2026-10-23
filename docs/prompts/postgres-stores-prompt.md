# Task: connect Arya's quiz and analytics logic to Supabase

You are working in this repo on the branch `feat/aparna-backend`. Do ONLY the part the user names ("Part A" or "Part B"). When it is done, stop and report; do not start the other part.

## Read first

- docs/api-contract.md: sections 1, 7 and 8 are the targets (conventions, quizzes and attempts, CO sheet and analytics)
- backend/migrations/001_init.sql: the tables (quizzes, quiz_questions, quiz_attempts, student_co_scores, questions, course_outcomes, enrollments, students)
- backend/app/services/quizzes.py: the `QuizStore` protocol, the record dataclasses and the business rules (do not change the rules)
- backend/app/services/co_analytics.py: the `AnalyticsStore` protocol
- backend/app/routers/quizzes.py and backend/app/routers/co_sheet.py: the handler classes (`QuizRouterHandler`, `COSheetRouterHandler`). Their methods take `current_user` and return `(status_code, body)`.
- backend/app/engine/co_math.py: `COConfig`, `StudentInfo`, `AttemptScore`
- backend/app/routers/quizzes_admin.py: already provides POST /quizzes, POST /quizzes/{id}/questions, POST /quizzes/{id}/publish, GET /quizzes and GET /quizzes/{id} on Supabase. Keep those routes. Do not duplicate them.
- backend/app/deps.py (`get_current_user`) and backend/app/db.py (`get_conn`)

## Hard rules

- Do not change the schema or add migrations. If you think a table or column is missing, STOP and tell me what and why.
- Do not change Arya's business logic in `services/` or `engine/`. Write adapters around it.
- The current user comes only from `get_current_user()`. Never read a user, role or USN from the request body or query.
- Errors use the contract format `{"error": {"code", "message"}}`. Reuse `AppError` from backend/app/errors.py, or convert the handler's `(status, body)` tuple into a JSONResponse.
- Never read, print or open `.env`. Never run git commands. Never create data outside pytest tests. Do not use `python -c` to write to the database.
- Keep the existing import style and run with `PYTHONPATH=backend:.`.
- Tests use unique data (random suffix on USNs and emails) and delete every row they create, even if the test fails. Run only the tests for the part you are working on, because each test talks to a remote database and is slow.

## Part A: quizzes, attempts and scores

1. Create `backend/app/stores/postgres_quiz_store.py` with `PostgresQuizStore(conn)` implementing every method of the `QuizStore` protocol using SQLAlchemy Core `text()` queries.
   - Map `QuestionRecord` from `questions` joined to `course_outcomes` (for `co_number`), and keep the `position` order from `quiz_questions`.
   - `answers` is stored as jsonb `{question_id: option_index}`.
   - `save_attempt` inserts or updates. If the database rejects a third attempt or a duplicate (unique or check violation), raise `AttemptLimitReachedError` so the user gets `ATTEMPT_LIMIT_REACHED`.
   - `save_co_scores` upserts on `(attempt_id, co_id)`. `update_co_score_counted` updates the `counted` flag.
2. Register these routes with FastAPI, calling `QuizRouterHandler` with a `PostgresQuizStore` built from the request's `get_conn` connection (commit at the end of a successful request, roll back on error):
   - `POST /quizzes/{id}/attempts` (student)
   - `GET /attempts/{id}` (student, own attempt)
   - `PUT /attempts/{id}/answers` (student, own attempt)
   - `POST /attempts/{id}/submit` (student, own attempt)
   - `GET /attempts/{id}/review` (student, own submitted attempt)
   - Put them in a new file `backend/app/routers/attempts.py` and add it to the list in `backend/app/main.py`. Do not remove the existing `quizzes_admin` or `quizzes` entries.
3. Extend `GET /quizzes?subject_id=` so that for a student it returns only published quizzes for subjects they are enrolled in, each with `attempts_used` and `attempts_left`. Faculty keep the current behaviour.
4. Safety checks to enforce and test:
   - A student never receives `correct_option` or `explanation` before submitting.
   - Another student's attempt returns 403 or 404.
   - A third attempt returns `ATTEMPT_LIMIT_REACHED`; a quiz before opening returns `QUIZ_NOT_OPEN`; after closing `QUIZ_CLOSED`; unpublished `QUIZ_NOT_PUBLISHED`.
5. Tests in `tests/backend/test_attempts.py` covering: start, resume after a refresh (`GET /attempts/{id}`), saved answers persist, submit returns scores and writes `student_co_scores` rows, both attempts allowed and the third refused, closed and not-open quizzes, masking of correct answers, and cross-student access.

When done, report the commands to run the tests and the results (pass and fail counts). Then stop.

## Part B: CO sheet and analytics (only when told)

1. Create `backend/app/stores/postgres_analytics_store.py` with `PostgresAnalyticsStore(conn)` implementing the `AnalyticsStore` protocol.
   - Read `COConfig` from `course_outcomes`, `StudentInfo` from `enrollments` joined to `students` (USN, name, section), and `AttemptScore` from `student_co_scores`. Respect the `counted` flag and the `ATTEMPT_RULE` setting that `engine/settings.py` already reads.
2. Register routes in a new `backend/app/routers/co_analytics.py` using `COSheetRouterHandler`, faculty only except where the contract says otherwise:
   - `GET /subjects/{id}/co-sheet`
   - `GET /subjects/{id}/co-summary`
   - `GET /subjects/{id}/cos/{co_id}/drilldown`
   - `GET /subjects/{id}/weak-cos`
   - `GET /subjects/{id}/co-sheet/export` (returns an .xlsx download)
   - `GET /students/me/progress` (student)
   - `GET /students/{usn}/progress` (faculty, or a student asking for their own USN; any other USN returns 403)
   - A faculty member may only read subjects they own.
3. Tests in `tests/backend/test_co_analytics.py`: build a tiny dataset (2 students, 2 COs, known marks), check the sheet and summary against numbers you computed by hand, check that changing one answer changes the sheet, the weak-CO flag, the Excel download opens with openpyxl, and a student token gets 403 on faculty endpoints and on another student's progress.

When done, report the commands and results. Then stop.
