# Arya: changes. How to apply

Unzip over the repo root (paths match the repo), or `git apply arya-changes.patch`.
Not touched: `stores/`, `attempts.py`, `quizzes_admin.py`, `docs/team/aparna.md`, `docs/team/danwin.md`, `docs/api-contract.md`, migrations, `frontend/`, `ai/`.

New
- backend/app/pg/ : Postgres stores and access helpers
- backend/app/services/ai_glue.py : Token Factory glue with code-only fallbacks, logs to agent_logs
- seed/seed.py : `python -m seed.seed --yes` (`--remove` deletes only its own rows)
- tests/backend/test_arya_integration.py : 29 integration tests
- tests/unit/conftest.py : placeholder env vars for unit tests
- docs/arya-integration-notes.md : decisions, behaviour, contract differences, open questions
- docs/message-to-aparna-from-arya.md : the message to send
- docs/submission-draft.md : project description, requirement table skeleton, feedback notes, video plan

Changed
- backend/app/main.py : five router lines
- backend/app/routers/{upload,co_sheet,study,calendar,usage}.py : live routes appended
- backend/app/services/qa.py : stopword filter, "not in the slides" becomes a refusal
- tests/unit/test_routers.py : "now" relative to the clock (the fixed date had expired)
- README.md : seed, demo data and test instructions
- docs/decisions.md : update under #1 (retrieval)
- docs/team/arya.md : status table and two open questions (checkboxes untouched)

Demo logins after seeding (invented): raman@lakshya.edu / Demo@12345, student 1XX23CS001 / 123456.
Do not run the seed on the shared database until the team agrees. See TEST_RESULTS.md for what was and was not verified.
