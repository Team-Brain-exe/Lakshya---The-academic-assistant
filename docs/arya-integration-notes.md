# Arya's integration notes (28 Oct 2026)

Status and decisions for the routes Arya wired to Postgres. Written for Aparna and Danwin.
Nothing below has been run on the hosted Supabase database or Render.

## 1. Ownership conflict to settle (frontend and tasks 8 to 13)

The three team files and Aparna's message do not agree. No file was changed to resolve this.

| Source | What it says about screens and integration |
|---|---|
| `docs/team/arya.md` | Arya owns backend logic only. No screens, no frontend. |
| `docs/team/aparna.md` | Tasks 8 to 13 are Aparna's: setup/upload/coverage, roster, quiz builder, attempt, progress and CO sheet screens. |
| `docs/team/danwin.md` | Tasks 8 to 13 are Danwin's, a different list: app shell and login, chat, study/Q&A/flashcards, review, calendar and cost page. It also gives him connecting the upload and quiz screens to the pipeline. |
| Aparna's message to Arya | Asks Arya to take "the screens and integration (tasks 8 to 13)". |

The same task numbers mean different work in `aparna.md` and `danwin.md`. Nobody owns the frontend API client
(`frontend/src/lib` has no `fetch` and no `VITE_API_URL`). Decision needed: one owner for the API client,
and one list of screens per person.

## 2. What was added (all in new files or appended routes)

- `backend/app/pg/`: Postgres stores for analytics, chunks and retrieval, calendar, study plan, flashcards and notes, usage, plus access helpers (`subject_for_faculty`, `subject_for_student`, `module_for_user`, `as_uuid`).
- `backend/app/services/ai_glue.py`: Token Factory glue. Without a key every feature falls back to code only; every provider call is written to `agent_logs` with token counts.
- Live routes in `upload.py`, `co_sheet.py`, `study.py`, `calendar.py`, `usage.py`. The handler classes and their unit tests are kept.
- `main.py`: five lines, after `attempts.router`.
- `seed/seed.py`, and `tests/backend/test_arya_integration.py` (29 tests).

Not touched: `stores/`, `attempts.py`, `quizzes_admin.py`, migrations, `docs/team/aparna.md`, `docs/team/danwin.md`, `docs/api-contract.md`, `frontend/`, `ai/`.
`routers/quizzes.py` is still an empty scaffold registered after `quizzes_admin.router`; it can be deleted from the router list.

## 3. Behaviour worth knowing

- **Access:** faculty only reach subjects they own (anything else is 404, not 403, so ids are not leaked); students only reach subjects they are enrolled in and only their own USN. Calendar events for one section are hidden from the other section.
- **Upload runs as a background task.** `POST /modules/{id}/upload` returns 202 `processing` at once; the job commits status changes so `GET /modules/{id}/status` shows `processing`, then `done` or `failed` with a reason. A second upload while processing returns 409. Re-uploading replaces the module's chunks. Single worker only (the task runs in the web process). The uploaded file is parsed in memory and not kept; only its name is stored.
- **CO sheet vs `counted`:** the sheet re-applies `ATTEMPT_RULE` in code over the per-attempt `student_co_scores` rows, the same setting Aparna's submit uses to set `counted`. Tests check there is exactly one counted row per student and CO and that it equals the sheet. If the rule is ever changed in config, old `counted` flags are not rewritten, but the sheet follows the config.
- **Slide Q&A** uses keyword retrieval over Postgres chunks (see `decisions.md` #1). With no AI key it answers by quoting the best slide; with a key the model may only answer from the retrieved slides, and "not in the slides" becomes a refusal.
- **Study plan:** slides and flashcards are linked in code from the database; the model only writes the recommendation text. A CO the student has no score for counts as weak (`services/study_plan.py` says so). Example: the seeded student 1XX23CS060 gets a plan for CO3 to CO6. Product question below.
- **Seed content is small:** 13 slides, 10 approved questions, 4 modules, 2 quizzes. Enough for the sheet and weak-CO story; thin for a Q&A demo. Upload a real deck for the video.

## 4. Differences from `docs/api-contract.md` (Aparna keeps that file)

- `GET /subjects/{id}/co-sheet`: `columns` holds labels (`"CO1"`, `"CO2"`), not numbers. Rows also carry `section`, `total_obtained`, `total_max`, `total_pct`, and the response has an extra `averages`. Rows' `co_scores` is keyed by label and is `null` for a CO the student has not been assessed on.
- `GET /subjects/{id}/coverage`: extra `message` field.
- `GET /students/.../progress`: extra `name`, `section`, `subject_id`, and per-CO `marks_obtained`, `max_marks`, `attained` (false when unassessed, with null marks and percentage).
- `GET /subjects/{id}/co-summary`: extra `threshold_pct`, `enrolled`, `attempted`, `target_met`, `gap`.
- Inner shapes marked TBC: the drill-down returns the students and questions behind the CO; the study plan is `{id, student_id, subject_id, weak_co_ids, plan: {title, weak_cos, steps: [{co_number, goal, recommendation, slides, flashcards}]}, generated_at}`.
- `POST /events` and the other event routes return the event with `id, subject_id, type, title, starts_at, ends_at, section, quiz_id, module_id`.
- Errors use `AppError` and the contract's error shape.

## 5. How it was tested, and what was not

See `TEST_RESULTS.md` in the package. In short: 165 unit tests, Aparna's 96 backend tests and 29 new integration tests pass on a local Postgres 16
(migrations 001 to 003, no Supabase roles, no Token Factory key). Not verified: the hosted database, migration 004 grants, Render, any real
Token Factory call, the frontend, concurrent use. Do not describe database integration as verified until the same tests pass against the hosted database.

## 6. Open questions

1. Frontend and tasks 8 to 13 ownership (section 1).
2. Danwin: is keyword retrieval acceptable, or is there an embedding model ID? (`decisions.md` #1)
3. Faculty: should a student's study plan include COs they have not been assessed on yet?
4. Faculty: Excel format. The export is a simple USN, name, section, CO%, total sheet plus a class summary sheet.
5. Whether to run the seed on the shared Supabase database, and when. It adds a subject, 60 students and one faculty login; `--remove` deletes exactly those rows.
