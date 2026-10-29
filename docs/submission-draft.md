# Submission draft (Arya), 28 Oct 2026

A working draft for the submission form. Items marked **[CONFIRM]** depend on something I cannot see from the repo.
**No official must-have list or judging rubric is in the repository**, so the mapping table below covers only the items
mentioned in the team messages. Paste the organisers' list into it before submitting; do not treat it as complete.

## 1. Project description (draft)

**Lakshya: the academic assistant.** Track: Best Apps and Agents. [CONFIRM the exact track name on the form]

Faculty who report Course Outcome (CO) attainment today build the sheet by hand from quiz marks. Lakshya turns
lecture slides and quiz attempts into that sheet. A faculty member uploads a slide deck; the app splits it into slide
chunks and links each chunk to the subject's COs. AI drafts quiz questions; **a faculty member approves every question
before any student can see it.** Students attempt published quizzes (two attempts per quiz), and the app computes
per-CO marks, a class CO sheet, the number of students above and below the threshold, and a weak-CO flag for any CO below
its target. The sheet exports to Excel. Students see only their own progress, and get slide-grounded Q&A that cites
the slide or refuses, flashcards and notes per module, and a study plan built around their weak COs.

Design rules that the code enforces and the tests check:
- **No LLM computes a mark.** Grading, CO totals, attainment and the weak-CO flag are plain code with unit tests.
- **AI generates, humans approve.** The database refuses to publish a quiz that contains an unapproved question.
- **A student only ever reaches their own data**, taken from the login token, never from the request.
- **AI runs once per module upload**, not once per student. Flashcards and notes are generated per module.
- Synthetic data only: invented names and USNs.

Where the sponsors' technology is used **[CONFIRM with Danwin before writing this on the form]**:
- **Nebius Token Factory:** all AI calls go through one client (`ai/token_factory.py`): CO tagging at upload, question
  generation, slide Q&A, flashcards and notes, study-plan wording. Every call is logged to `agent_logs` with token counts,
  which feeds the usage summary.
- **NVIDIA Nemotron models:** the model IDs are set by environment variables (`MODEL_TAGGING`, `MODEL_GENERATION`,
  `MODEL_REASONING`, `MODEL_AGENT`). As of 28 Oct the repo shows no real run against a Nemotron model; Danwin's Nemotron test
  tasks are unchecked. Name the models only after they have actually been called.
- **Nebius hosting:** the upload pipeline is a plain function that could run as a Nebius Serverless Job, but
  `decisions.md` marks that optional. Do not claim Nebius hosting unless the demo is actually deployed there. The backend
  deploy config targets Render.

## 2. Requirement mapping (only the items named in the team messages)

| Requirement | Where it is met | Status on 28 Oct |
|---|---|---|
| Working hosted demo URL | Backend on Render (Aparna), frontend host not decided in the repo | **Not live.** README says "TODO: URL". |
| Public repo with a license | MIT, `LICENSE` | Done |
| README with run instructions | `README.md` (setup, seed, tests, deploy) | Done, needs a final read-through once the demo URL exists |
| Demo video under 3 minutes, public on YouTube, no copyrighted music or third-party trademarks | Not made | **Not started.** Owner not agreed. |
| Track named, and where Nemotron, Token Factory and Nebius are used | Section 1 above | Draft. **[CONFIRM]** Nemotron and Nebius usage |
| Working end-to-end chain, not slides | Backend routes tested locally (see `TEST_RESULTS.md`) | Backend only, local database only. No frontend API client yet, so no screen is connected. |
| Agent | `ai/`, `agent_tools.py`; `POST /agent/chat` | **Not registered in `main.py`.** Planned in the contract. Do not present as working. |
| [add the organisers' remaining must-haves here] | | |

## 3. Feedback notes (my part, for the shared form)

Only what I actually did, so nothing here is about the platform's quality:
- I built the Q&A, flashcard and study-plan features against Danwin's client behind a small callable interface, so they run with no key
  and fall back to slide text. That made them testable offline with a fake client; real-model behaviour is untested.
- Retrieval: no embedding model was confirmed, so I used keyword scoring over Postgres chunks (`decisions.md` #1). It cannot match
  meaning, only words.
- **[TO ADD after a real-credential test]:** latency, JSON validity rate, token counts per step (the usage summary will show these), and
  anything that surprised us on Token Factory.

## 4. Demo video plan (about 2 min 45 s), using only flows that work

Prerequisite: the hosted demo is up, seeded, and a frontend is connected (neither is true yet). Seeded logins are in the README.

| Time | Scene | Shows |
|---|---|---|
| 0:00 to 0:15 | Problem | Faculty build the CO sheet by hand |
| 0:15 to 0:40 | Faculty uploads a deck | Status moves to done; coverage per CO, with a warning where a CO has no slides |
| 0:40 to 1:05 | Question review | AI-drafted questions, faculty approves; an unapproved question cannot be published |
| 1:05 to 1:35 | CO sheet | Sheet, class summary, CO3 flagged weak (56.7% against a 60% target), drill-down to the students and questions |
| 1:35 to 1:50 | Excel export | The downloaded sheet matches the screen |
| 1:50 to 2:15 | Student view | A student sees only their own progress; one attempt, then the sheet changes |
| 2:15 to 2:35 | Study help | Slide Q&A with a cited slide, then a refusal for an off-topic question; study plan for the weak CO |
| 2:35 to 2:45 | Close | Rules: AI drafts, humans approve, no AI computes a mark |

Record with the seeded data only. Check the video for real names, keys in screenshots, third-party logos and music before uploading.

## 5. Still to decide

- Who records and edits the video, and who fills in the form.
- The frontend owner (see `arya-integration-notes.md`), because the demo needs screens.
- The real submission deadline.
