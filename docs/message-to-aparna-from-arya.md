# Message to Aparna

**Subject: My routers are wired to Postgres and tested locally. Please review, and I need four answers.**

Hi Aparna,

I pulled `main` and read your message. My part is on a branch, ready for you to review. All numbers below are from a local Postgres 16 with migrations 001 to 003. **I have not run any of it on the shared Supabase database or on Render, so please don't treat integration as verified until we do.**

## What is on my branch

- The five unwired routers now have real routes: `upload.py`, `co_sheet.py`, `study.py`, `calendar.py`, `usage.py`. Postgres stores are in a new package, `backend/app/pg/`.
- `main.py`: five lines, added after `attempts.router`, as you suggested. I am the only one touching those lines.
- `seed/seed.py`, a runner that works against a real database (details below).
- `tests/backend/test_arya_integration.py`: 29 tests. Results: 165 unit tests pass, your 96 backend tests still pass, and the 29 new ones pass.
- I did **not** touch `quizzes_admin.py`, `attempts.py`, `stores/`, migrations, `docs/api-contract.md` or the team files. I only used your tables and your `counted` column.
- `docs/arya-integration-notes.md` has the details. `TEST_RESULTS.md` lists what was and was not tested.

## Your five requests

1. **Integration plan:** done locally as above. Provisional targets (subject to the real submission deadline): your review by Oct 29, then we run the same tests against the hosted database together.
2. **`main.py`:** one line per router after `attempts.router`, already done.
3. **Seed:** `python -m seed.seed --yes` loads one faculty login, 60 students, a subject with 6 COs, 4 modules, 13 slides, 10 approved questions, 2 published quizzes, 118 attempts, events, flashcards and notes. Invented names and USNs only. The old SQL failed on a real database: it published quizzes before their questions existed, and its password hashes were placeholders so no login worked. Both are fixed. Running it twice adds nothing, and `--remove` deletes only the rows the seed created. Demo logins are in the README.
4. **Team docs:** I updated `arya.md` with a status table. I did **not** move tasks 8 to 13 into my file, because the files disagree (next section).
5. **Missing or wrong endpoints:** nothing missing from your side. Small differences from the contract are listed in section 4 of the notes. For example, `co-sheet` returns `columns` as `["CO1", ...]`, not numbers, and has a few extra fields.

## Four questions

1. **Frontend ownership.** `arya.md` gives me no screens. `aparna.md` lists tasks 8 to 13 under you. `danwin.md` uses the same numbers for a different list (login, chat, study screens, calendar, cost page) and gives Danwin the upload and quiz screen integration. Your message asks me to take them. Nobody owns the frontend API client. Can we agree one owner for the API client and one list of screens per person? I would like Danwin's view before I commit to anything.
2. **Hosted database.** Can you (or I, with the connection details sent privately) run `pytest tests/backend` on the shared Supabase database, and decide when to run the seed there? I will not seed it until you agree. The seed adds one subject, 60 students and one faculty login.
3. **Migration 004.** Your grants for `anon` and `authenticated` need Supabase roles, so I could not test them locally. Please confirm my routes still work after 004 on Supabase.
4. **Delete `quizzes.router`?** It is an empty scaffold registered after `quizzes_admin.router`. I would drop it from the list, but it is your call.

## Things to confirm that affect your code

- The CO sheet re-applies `ATTEMPT_RULE` in code over the per-attempt rows, the same setting your submit uses for `counted`. Tests check there is exactly one counted row per student and CO and that it equals the sheet. Does anything else you built treat `counted` as the source of truth?
- A student asking for another student's progress gets 403, as in the contract. Faculty only see subjects they own, and I return 404 for a subject that is not theirs.
- Study plans treat a CO the student has not been assessed on as weak. That is how the service was written; I flagged it in the notes as a question for faculty.

## Token Factory

Not confirmed, so I used the fallback paths. With no key, tagging leaves chunks untagged (the upload still succeeds), answers quote the best slide, and flashcards and plans use slide text. AI-backed paths were tested only with a fake client. When the key and model IDs are confirmed, we should test them separately; nothing about them is in the repo.

## Still to do

- Run the tests on the hosted database, and fix whatever they find.
- The frontend API client and screens, once ownership is agreed.
- Submission work: description, requirement-mapping table, feedback notes. I propose we agree who records and edits the video once the demo runs.

Thanks,
Arya
