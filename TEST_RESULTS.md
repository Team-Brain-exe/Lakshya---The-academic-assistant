# Test results (Arya)

Run on 28 Oct 2026 in a sandbox, not on the team's Supabase database or Render.

| Suite | Result |
|---|---|
| `tests/unit` (no database) | 165 passed |
| `tests/backend` (Aparna's, unchanged) | 96 passed |
| `tests/backend/test_arya_integration.py` (new, real Postgres) | 29 passed |

After the runs, only the seed rows remained (the tests removed their own).

## Environment
- PostgreSQL 16 on localhost, migrations 001, 002 and 003 applied.
- Migration 004 was NOT applied: it grants to the Supabase roles `anon` and `authenticated`, which do not exist locally. Those grants are untested.
- Python 3.14.5, SQLAlchemy 2.0.36, Psycopg 3.2.10, FastAPI 0.115.6. The full test run completed locally on 28 Oct 2026: 290 passed. The dependency versions used for this run may differ from the pinned project requirements.
- No Token Factory credentials. AI paths ran on fallbacks, or on a fake client that returns canned text and token counts.

## What the 29 integration tests cover
- Permissions: no token (401), student on faculty routes (403), another faculty member (404), unenrolled student (404), a student reading another student's progress (403, any USN casing), malformed ids (404 not 500), section-filtered calendar.
- Upload status: pending -> processing -> done, a job that never finishes blocks a second upload (409), a corrupt file ends `failed` with a reason and a good re-upload recovers, input validation, a tagging failure does not fail the upload, tags and coverage counts, re-upload replaces chunks.
- Quiz submission and sheet consistency: sheet equals the `counted` flag (exactly one counted attempt per student and CO), changing one answer moves the sheet, summary, weak-CO flag and the `counted` row, a third attempt is refused, unattempted students show no score, section and module scope, drill-down contents, Excel export equals the on-screen sheet.
- Slide Q&A (cites slides, refuses off-topic), study material once per module, study plan with only the weak CO's slides, calendar create/list/move/delete/validation and cross-faculty protection, publish creates its event, usage totals per step, AI failure falls back and is logged.

A mutation check was run: with the faculty ownership check deliberately broken, both cross-faculty tests failed. The check was restored.

## Not verified
- The hosted Supabase database and the Render deployment.
- Migration 004 grants.
- Real Token Factory calls (tagging, answers, flashcards, plan wording).
- Concurrent users, and upload of large decks (25 MB is the limit).
- The frontend (no API client exists yet).
- The seed on the hosted database (it was run only on the local one).
