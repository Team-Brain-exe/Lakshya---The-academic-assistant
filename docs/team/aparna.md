# Aparna: Database, API, Deployment and CO Screens

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

You own the database schema, the authentication, the question endpoints, the API contract, and the agent tools that read CO data. You also own deployment, and the screens for setup, upload, roster, quiz building, student attempts, student progress, and the CO sheet and dashboard.

Start with the schema and the API contract. Arya's grading and Danwin's review screen both build on them.

## Your tasks

### 1. Database schema and constraints (2 points)

- [ ] Create the Supabase project. Write the schema from brief section 10: Subject, CourseOutcome, Module, ContentChunk, a chunk-to-CO join table, Question, Flashcard, Note, Student, Enrollment, Quiz, QuizAttempt, StudentCOScore, Event, User, AgentLog.
- [ ] Enforce the constraints in the database, not only in code: attempt number is 1 or 2 per student per quiz, a question must be approved before it can appear in a published quiz, and USN is unique per enrollment.

### 2. Auth backend (1 point)

- [ ] Hash PINs with bcrypt or argon2. Student login is USN plus PIN. Faculty login is separate. The role goes into the session token.

### 3. Subject, CO, module and roster backend (2 points)

- [ ] CRUD endpoints for subjects, COs (CO1 to CO6 with a threshold), and modules.
- [ ] Roster CSV upload: parse USNs, create Student and Enrollment rows, and return a report of duplicates and bad rows.

### 4. Question endpoints (2 points)

- [ ] List draft questions by module and CO, edit them, approve them, reject them, and create them manually.

### 5. Agent tool functions for CO data (2 points)

- [ ] Implement `get_co_attainment`, `find_weak_COs`, `get_student_progress`, `export_sheet`, and `generate_quiz`. The last one calls Danwin's generation function and saves the drafts.
- [ ] The logged-in user comes from the server session, never from model output. Student tools can only read that student's own USN.
- [ ] Validate every argument against Danwin's schemas before running anything.

### 6. API contract (1 point)

- [ ] In the first few hours, write `docs/api-contract.md`: endpoints, request and response shapes, the auth header, and the error format. Danwin and Arya code against it.

### 7. Hosting and deployment (2 points)

- [ ] Choose the hosting target (free tier or Nebius Serverless Endpoints) and write it into the README.
- [ ] Deploy the backend and the frontend. Check the hosted URL in an incognito window.
- [ ] Own the demo URL through judging.

### 8. Setup, upload and coverage screens (3 points)

- [ ] Subject and CO setup form: create a subject and define CO1 to CO6 with descriptions and thresholds.
- [ ] Module upload: PPT file picker and a progress state while tagging runs.
- [ ] Coverage view: the chunk count per CO, with a warning when it is zero.

### 9. Roster upload screen (1 point)

- [ ] CSV upload with a preview of rows and errors before confirming.

### 10. Manual question form and quiz builder (2 points)

- [ ] Manual question form for faculty-written questions.
- [ ] Quiz builder: pick approved questions, set open and close times, and publish.

### 11. Student attempt and result screens (2 points)

- [ ] Attempt screen: show attempts left (maximum 2), let the student submit, and keep answers if the page refreshes.
- [ ] Result screen: the score for each CO after the attempt.

### 12. Student progress and quiz review screens (2 points)

- [ ] CO progress as a bar or radar chart.
- [ ] Quiz review: each wrong answer with its CO and an explanation.

### 13. CO sheet and dashboard screens (4 points)

- [ ] CO marks sheet: a table of student × CO × total, a module and semester toggle, sorted by USN, and an export button that calls Arya's export endpoint.
- [ ] Faculty dashboard: average per CO as a bar chart, a score distribution, weak COs highlighted against the target, and a click-through drill-down.

### 14. README backend section (1 point)

- [ ] Explain how grading works and what the LLM never does. Describe the database setup.

## Submission work (outside the points)

- Record the setup, upload, sheet and dashboard screens for the video.

## Hand-offs

You depend on:
- Arya: the upload pipeline, the grading and attempt endpoints, and the CO sheet and dashboard data.
- Danwin: the tagging and generation functions, and the tool schemas.

You are depended on by:
- Danwin: the database, the question endpoints, the CO-data tools, and the deployed backend.
- Arya: the database schema, which grading and the sheet read from.

## Done when

- The API contract is committed and both Danwin and Arya have read it.
- The full demo chain works in the hosted app: upload, tag, approve, publish, attempt, sheet.
- A student token cannot fetch another student's data, through the API or the agent.
