# Arya: Data Pipeline, Grading, CO Sheet and Study Features

## Team at a glance

| Person | Area | Effort points |
|---|---|---|
| Danwin | AI and agent, integration, AI-facing screens | 27 |
| Aparna | Database, API, deployment, CO screens | 27 |
| Arya | Data pipeline, grading, CO sheet, study features, seed data | 27 |

Effort points: small task = 1, medium = 2, large = 3. Each person has 27 points, so the technical work is split equally. Submission tasks sit outside the points (see the end of this file).

## Ground rules (all three of us)

- AI generates, humans approve. No generated question reaches a student before faculty approval.
- Grading and CO math are plain code. No LLM computes a mark.
- Synthetic data only. No real student records in the repo or the video.
- Students only ever reach their own data, through the UI and through the agent.

## Your area

You own the backend logic that turns slides and quiz attempts into numbers: the PPT pipeline, grading and CO marks, the CO sheet and its export, and the slide-grounded study features. You also own the calendar backend, the usage log, and the seed data for the demo.

Grading is the part the pitch depends on, so its unit tests need to be exact. You build the Q&A, study plan and flashcards on top of Danwin's Token Factory client and prompts, so agree those interfaces with him in the first build.

## Your tasks

### 1. Repo, license, environment and README skeleton (3 points)

- [ ] Create a public GitHub repo with an MIT or Apache 2.0 license, visible in the About section. Add `.gitignore`.
- [ ] Set up the layout: `backend/`, `frontend/`, `ai/`, `notes/`, `docs/`, `seed/`, `tests/`.
- [ ] Add `.env.example` with every variable: Token Factory key, Supabase URL and key, database URL, and session secret. Never commit real values.
- [ ] Write a README skeleton with sections for Nemotron, Token Factory and Nebius, plus setup and run commands.

### 2. Seed data (1 point)

- [ ] Seed script: 1 subject, 6 COs, 4 or 5 modules, about 60 students with fake USNs, a realistic score spread, a few students clearly weak in CO3, and 1 or 2 approved quizzes from Danwin.
- [ ] Run the seed on the hosted database before the video is recorded.

### 3. PPT parsing, chunks and coverage endpoint (3 points)

- [ ] Use python-pptx to split the uploaded slides into ContentChunks, with slide number and text.
- [ ] Call Danwin's tagging function and store the chunk-to-CO links. An untagged chunk must not fail the upload.
- [ ] Coverage endpoint: the number of chunks per CO, with a warning when it is zero.
- [ ] Write the pipeline as a plain function, so it can move to Nebius Serverless Jobs later.

### 4. Grading and CO marks (2 points)

- [ ] Grade in code: compare each answer with the correct option and sum the marks.
- [ ] Split the marks by `question.co` and write StudentCOScore rows.
- [ ] Unit tests for the formula in brief section 6, including edge cases: a CO with no attempted questions, one attempt, and two attempts.
- [ ] Put the attempt-counting rule (best, latest or average) in config. Default to best until faculty confirm, and say so in the README.

### 5. Quiz publish and attempt endpoints (2 points)

- [ ] Build a quiz from approved questions, set open and close times, and publish. Publishing refuses any unapproved question.
- [ ] Start an attempt (maximum 2), submit answers, grade them with item 4, and return the score.

### 6. CO sheet, class summary, drill-down and weak-CO flag (5 points)

- [ ] Sheet endpoint: student × CO × total, per module and per semester.
- [ ] Class summary endpoint: average per CO, the count above and below the threshold, and whether each CO met its target.
- [ ] Drill-down endpoint: for one CO, the modules, questions and students behind the number.
- [ ] Weak-CO flag for any CO below target. The agent's `find_weak_COs` tool uses it.
- [ ] Test: change one answer and check that the sheet updates correctly.

### 7. Excel export (1 point)

- [ ] Export the sheet with openpyxl. Match the university's format once faculty confirm it.

### 8. Slide-grounded Q&A (3 points)

- [ ] Agree the retrieval approach with Danwin in the first build: pgvector or in-memory.
- [ ] Retrieval endpoint that returns the top chunks for a question, with their slide numbers.
- [ ] Implement `answer_from_course_material(question)` on top of Danwin's client. Answer only from the retrieved chunks, cite the slide, and refuse when nothing matches.

### 9. Study plan (2 points)

- [ ] Implement `build_study_plan(usn)`: take the student's weak COs from item 6, find the matching slides, and build the plan with Danwin's client.
- [ ] Store the plan with its linked slides and flashcards.

### 10. Flashcards and notes (2 points)

- [ ] Generate flashcards and notes once per module, not once per student, using Danwin's client.
- [ ] Store them in the Flashcard and Note tables from Aparna's schema.

### 11. Calendar backend and calendar tools (2 points)

- [ ] Events table: type, date and time, subject, section, linked quiz or module, and created by.
- [ ] Endpoints to create, list and move events, with role checks.
- [ ] Implement the `schedule_event` and `list_events` tool functions for the agent.
- [ ] A published quiz can create its event automatically. Agree this with Aparna's publish step.

### 12. Usage logging (1 point)

- [ ] Log every AI call and every tool call to AgentLog, with the token counts Danwin returns.
- [ ] Provide the totals per step that Danwin's cost page reads.

## Status (28 Oct 2026)

Checkboxes above are left as written until each item is confirmed on the hosted database. "Tested" means
the integration tests in `tests/backend/test_arya_integration.py` pass on a local Postgres 16 with migrations
001 to 003; nothing here has been run on Supabase or Render yet.

| Task | State |
|---|---|
| 1 Repo, license, README | Done earlier. README seed and test sections updated. |
| 2 Seed data | Runner written and tested locally (`python -m seed.seed`). **Not yet run on the hosted database.** |
| 3 PPT parsing, chunks, coverage | Routes wired to Postgres and tested (upload status transitions, tags, coverage). Tagging was tested with a stub; **real AI tagging untested**. |
| 4 Grading and CO marks | Unit tests pass. Submission and the `counted` flag are Aparna's code; sheet consistency tested. |
| 5 Publish and attempts | Done by Aparna (`quizzes_admin.py`, `attempts.py`). Not mine to change. |
| 6 CO sheet, summary, drill-down, weak CO | Wired and tested, including "change one answer and the sheet moves". |
| 7 Excel export | Tested against the on-screen sheet. **Format not confirmed with faculty.** |
| 8 Slide Q&A | Wired with keyword retrieval (see decisions.md #1). Real AI answers untested. |
| 9 Study plan | Wired and tested. Open question: unattempted COs count as weak (see below). |
| 10 Flashcards and notes | Wired and tested (slide-text fallback). AI version untested. |
| 11 Calendar | Wired and tested. Quiz events are created by Aparna's publish. |
| 12 Usage logging | Wired and tested with a fake client. Real token counts untested. |

Not done: the frontend API client and screens, the submission work, and anything on the hosted environment.

## Submission work (outside the points)

- Write the project description. Name the track (Best Apps and Agents) and say where Nemotron, Token Factory and Nebius are used.
- Build the requirement-mapping table: each must-have mapped to where it is met, with no gaps.
- Compile the feedback notes from all three of us into the submission form.
- Assemble the video from the recordings the three of us make. It must be under 3 minutes, use no copyrighted music and no third-party trademarks, and be public on YouTube.
- Fill in the submission form.

## Open questions and owners

| Question | Owner |
|---|---|
| Submission deadline and final team size | Whole team |
| Which attempt counts: best, latest or average | You build the config; faculty decide |
| Real CO threshold and target attainment | Aparna stores them; confirm with faculty |
| Excel format the university uses | You |
| Retrieval for slide Q&A: pgvector or in-memory | Danwin and you, in the first build |
| Who keeps the demo URL up through judging | Aparna |
| Who owns the frontend API client and the screens (tasks 8 to 13)? `aparna.md`, `danwin.md` and Aparna's message disagree, see `docs/arya-integration-notes.md` | Whole team |
| Should a study plan include COs the student has not been assessed on yet? Today it does | Faculty and team |

## Hand-offs

You depend on:
- Danwin: the tagging and generation functions, the Token Factory client and prompts, and the tool schemas.
- Aparna: the database schema and the question endpoints.

You are depended on by:
- Aparna: the grading, sheet and dashboard data that her screens display.
- Danwin: the Q&A, study and calendar tools, and the usage totals for the cost page.

## Done when

- Grading and CO math unit tests pass, including the edge cases.
- The CO sheet matches a hand calculation on the seed data for one student and one CO.
- The Q&A answers cite slides and refuse when nothing matches.
- The Excel export opens and matches the on-screen sheet.
