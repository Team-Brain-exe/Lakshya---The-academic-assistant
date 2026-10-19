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

- [ ] Build `tag_content_with_COs(chunks, cos)`, returning a list of `{chunk_id, cos, confidence}`.
- [ ] Batch chunks to limit calls. Retry once on bad JSON. If it still fails, mark the chunk untagged. Never fail the whole upload.
- [ ] Return token usage per call, so Arya's usage log can record it.
- [ ] Commit the output schema to `ai/schemas/` before Arya builds the upload pipeline.

### 3. Quiz generation (2 points)

- [ ] Build `generate_quiz(module, co, difficulty, count)`, returning drafts with `status=draft` and `source=AI`.
- [ ] Validate every draft before review: 4 options, exactly 1 correct, the CO matches the request, no duplicate stems.
- [ ] Pre-generate and approve 1 or 2 quizzes for the demo. Give the approved set to Arya for the seed data.

### 4. Agent loop and tool schemas (3 points)

- [ ] Build the tool-calling loop in FastAPI: send the conversation and tool schemas to the model, run the tool it picks, return the result, and repeat until it answers.
- [ ] Cap the loop at about 6 steps so a confused model cannot spin forever.
- [ ] Write the JSON schema for every agent tool. Aparna implements the CO-data tools, and Arya implements the Q&A, study plan and calendar tools. You own the contracts.
- [ ] Write a system prompt for each role. The role decides which tools are offered. The server enforces the same check.
- [ ] Put the grounding rule in the prompt: every figure comes from a tool result, and the agent says it does not know when retrieval finds nothing.
- [ ] Make the faculty chain work in one message: find weak COs, generate a remedial quiz, propose a schedule.
- [ ] Schedule and move actions return a proposal. Nothing is saved until the user confirms.

### 5. Agent integration and role tests (2 points)

- [ ] Register every agent tool with the loop. Check that each schema matches its implementation.
- [ ] Write the role-scoping tests: a student who asks about another student's USN is refused, both through the API and through the agent. Report any failure to the owner of that tool.
- [ ] Confirm that every write the agent makes needs confirmation or review first.

### 6. Upload and quiz integration (4 points)

- [ ] Connect the upload screens to Arya's pipeline and Aparna's endpoints. Run the upload end to end with real slides, and confirm a failed tagging call does not break it.
- [ ] Connect the review, quiz builder and attempt screens to the quiz loop. Run the end-to-end check: generate, review, approve, publish, attempt, grade, and StudentCOScore written.
- [ ] Confirm that the backend blocks publishing an unapproved question.

### 7. Smoke-test script (1 point)

- [ ] In `tests/integration/`, write a script that logs in, sends one agent message, and exports one sheet. Run it the morning of submission.

### 8. App shell and login screens (1 point)

- [ ] Login screens for student (USN plus PIN) and faculty. Store the session and route each user by role.

### 9. Agent chat panel (2 points)

- [ ] Chat panel for both roles: message list, a loading state, and chips that show which tool ran (for example, "Called find_weak_COs").
- [ ] Confirmation card for schedule and move actions, with approve and cancel.
- [ ] Show a generated quiz draft with a link to the review screen.

### 10. Study, flashcard and Q&A screens (2 points)

- [ ] Study plan page, flashcards page, and a Q&A page that shows the slide citation.

### 11. Faculty review screen (2 points)

- [ ] List generated questions by CO. Let faculty edit the text, options and correct answer, then approve or reject each one.
- [ ] Show each question's source (AI or faculty) and its status.
- [ ] Uses Aparna's question endpoints.

### 12. Calendar screens (2 points)

- [ ] Month and week views for both roles, using Arya's event endpoints.
- [ ] Upcoming deadlines on the student home screen.

### 13. Cost page (1 point)

- [ ] Tokens per step, plus the before and after table, built from Arya's usage log.

### 14. README AI section and feedback notes (1 point)

- [ ] Explain where Nano, Super and Ultra are used and why.
- [ ] Write the Token Factory and NVIDIA model feedback for the submission form.

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
