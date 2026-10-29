# Danwin: AI, Agent, Integration and Screens

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

You own every call to Nebius Token Factory and the Nemotron models, plus the agent loop. You also make sure the parts connect: you run the end-to-end checks, the role tests and the smoke test. You build the screens that show AI output (chat, study plan, Q&A, flashcards, faculty review), along with the login screen and the calendar screens.

Start with item 1 on day one. Items 2 to 4 depend on the schemas, so commit those early so Arya and Aparna can build against them.

## Your tasks

### 1. Model testing and selection (2 points)

- [ ] Get Token Factory access working. Store the key in `.env` and never commit it.
- [ ] Test Nemotron Nano on CO tagging with 2 or 3 real slide decks. Check that output is valid JSON every run, that tags stay consistent across repeated runs, and that tags match what each slide covers.
- [ ] Test Nemotron Super on MCQ generation for one CO. Check for exactly one correct answer, the right CO tag, and plausible distractors. Read every question and count the failures.
- [ ] Test Super on tool calling with 2 or 3 dummy tools. Check the tool choice, argument validation, and that it continues correctly after a tool result.
- [ ] Write the model ID chosen for each task into config.
- [ ] Start `notes/feedback-log.md`: what worked, what broke, latency, JSON reliability.

### 2. CO tagging (2 points)

- [x] Build `tag_content_with_COs(chunks, cos)`, returning a list of `{chunk_id, cos, confidence}`.
- [x] Batch chunks to limit calls. Retry once on bad JSON. If it still fails, mark the chunk untagged. Never fail the whole upload.
- [x] Return token usage per call, so Arya's usage log can record it.
- [x] Commit the output schema to `ai/schemas/` before Arya builds the upload pipeline.

### 3. Quiz generation (2 points)

- [x] Build `generate_quiz(module, co, difficulty, count)`, returning drafts with `status=draft` and `source=AI`.
- [x] Validate every draft before review: 4 options, exactly 1 correct, the CO matches the request, no duplicate stems.
- [ ] Pre-generate and approve 1 or 2 quizzes for the demo. Blocked until Token Factory credentials/model IDs and faculty approval are available.

### 4. Agent loop and tool schemas (3 points)

- [x] Build the bounded tool-calling loop and FastAPI routes. `main.py` now installs the PostgreSQL runtime automatically when `.env` has HTTPS Token Factory settings plus `MODEL_AGENT` and `MODEL_GENERATION`; only faculty `generate_quiz` is bound today. Migration 005 is required. Analytics access still needs a persistent store adapter, and student Q&A/study/calendar handlers and proposal executors remain pending. Missing settings or migration returns `503 AGENT_NOT_CONFIGURED`; roles with no registered tools get a no-model unavailable reply.
- [x] Cap the loop at 6 model steps, 6 tool calls per request, and 3 tool calls in a single model response.
- [x] Publish JSON schemas for every agent tool in `ai/schemas/agent-tools.json`. The runtime binds Aparna's faculty quiz-draft handler; CO analytics still needs a persistent store adapter, and Arya's Q&A/study/calendar handlers remain pending.
- [x] Write a system prompt for each role. Tools are filtered by role in the server-side registry.
- [x] Put the grounding rule in the prompt: figures come from tool results; the agent says it does not know when retrieval finds nothing.
- [ ] Make the faculty chain work end to end in one message: find weak COs, generate a remedial quiz, propose a schedule. Waiting on live tool adapters.
- [x] Schedule and move actions return confirmation-gated proposals. No write handler runs until the user confirms.

### 5. Agent integration and role tests (2 points)

- [ ] Register every agent tool with a real implementation and verify schema matches. The registry builder omits missing handlers rather than exposing stubs.
- [x] Add agent-core and FastAPI route tests that refuse a student's attempt to pass another student's USN to `get_my_progress`, and reject role fields supplied in the request body. Test real DB tool-handler ownership once the adapters are registered.
- [x] Mutating agent actions are either reviewable drafts or confirmation-gated proposals.

### 6. Upload and quiz integration (4 points)

- [ ] Connect the upload screens to Arya's pipeline and Aparna's endpoints, then test with authorized real decks. Offline integration tests confirm malformed tagging JSON leaves chunks untagged without failing upload.
- [ ] Run the complete generate, review, approve, publish, attempt, grade, and StudentCOScore flow against the hosted app.
- [x] Confirm that the existing backend blocks publishing an unapproved question (covered by the current unit tests).

### 7. Smoke-test script (1 point)

- [x] Add `tests/integration/smoke_test.py` to log in, send one agent message, and export one sheet.
- [ ] Run it the morning of submission against a hosted app. It cannot run in this checkout until `SMOKE_BASE_URL`, faculty test credentials, a subject ID, and the agent runtime are configured.

### 8. App shell and login screens (1 point)

- [x] Student USN/PIN and faculty login forms, in-memory sessions, role-specific navigation, subject selector, and logout are implemented in `frontend/`. Tokens are not persisted in browser storage, so a page refresh requires sign-in again.

### 9. Agent chat panel (2 points)

- [x] Both roles have message history, loading/error states, tool chips, and suggested prompts.
- [x] Schedule/move proposals show approve/cancel; proposal IDs and statuses follow the backend contract.
- [x] Quiz draft cards link to question review. Live use still waits on registered agent tool handlers.

### 10. Study, flashcard and Q&A screens (2 points)

- [x] Study plan, flashcards, and slide-cited Q&A pages are implemented with loading/empty/error states. Endpoints are not all mounted in the current backend, so unavailable services are shown as errors instead of fake data.

### 11. Faculty review screen (2 points)

- [x] Questions are grouped by CO and filterable by module, status, and source; faculty can edit question text/options/correct answer/explanation and approve or reject.
- [x] Source and status chips are shown; the screen calls Aparna's question endpoints.

### 12. Calendar screens (2 points)

- [x] Month/week views are available for both roles; faculty can add/edit/move/delete events, students have read-only views.
- [x] Student home shows upcoming deadlines and CO progress when the backend returns them. Calendar/progress endpoints still need to be registered in the app.

### 13. Cost page (1 point)

- [x] Per-step token/call totals are displayed from the usage API when available. The before/after comparison is labeled "Not reported" until real measurements and per-module data are supplied; no savings are fabricated.

### 14. README AI section and feedback notes (1 point)

- [x] Explain where Nano, Super and Ultra are intended to be used and why; mark model selection as pending real evaluation.
- [ ] Write factual Token Factory and NVIDIA model feedback after authorized live tests. The feedback log records that no provider calls were run because credentials, model IDs, and slide decks are absent.

## Submission work (outside the points)

- Record the chat, study, Q&A and review screens for the video.

## Hand-offs

You depend on:
- Aparna: the database, the question endpoints, the CO-data tools, and the deployed backend.
- Arya: the upload pipeline, the grading and attempt endpoints, the Q&A, study and calendar tools, and the usage log.

You are depended on by:
- Aparna: the tagging and generation functions, and the tool schemas.
- Arya: the Token Factory client and prompts that the Q&A, study plan and flashcard features use.

## Done when

- Tagging returns valid JSON on the demo decks across repeated runs.
- Generated questions pass validation: one correct answer, correct CO.
- The agent completes the faculty demo chain from one message.
- The smoke test passes on the hosted app.
