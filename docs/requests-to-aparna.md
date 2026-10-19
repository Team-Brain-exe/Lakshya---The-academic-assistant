# Arya's requests to Aparna: endpoints and table columns

Aparna asked everyone to send the endpoints and table columns they need, so the schema and `docs/api-contract.md` can be written first. This is Arya's list, built from `arya.md`. Everything here is a request, not a decision: change anything that clashes with the schema or with Danwin's and the frontend's needs.

Ownership reminder: Aparna owns the schema, auth and the question endpoints. Arya owns the endpoints marked "Arya builds" below. Aparna writes them into the contract, and Arya implements them.

## A. Table columns Arya needs

Types are suggestions. Every table gets `id` (uuid) and `created_at`.

### Subject
`id`, `code`, `name`, `semester`, `faculty_user_id`, `target_attainment_pct` (class target, e.g. 60), `default_threshold_pct` (pass mark per CO, e.g. 60)

### CourseOutcome
`id`, `subject_id`, `number` (1 to 6), `description`, `threshold_pct`, `target_attainment_pct`

Unique on (`subject_id`, `number`). Per-CO threshold and target are needed for the weak-CO flag.

### Module
`id`, `subject_id`, `number`, `title`, `ppt_file_path`, `processing_status` (`pending` | `processing` | `done` | `failed`), `processing_error`, `processed_at`

Arya needs the status columns so the upload screen can show progress and the pipeline can report failures.

### ContentChunk
`id`, `module_id`, `slide_number`, `text`, `tag_status` (`tagged` | `untagged`), `embedding` (nullable, only if pgvector is chosen, see `docs/decisions.md`)

### ChunkCO (join table)
`chunk_id`, `co_id`, `confidence` (numeric)

Primary key (`chunk_id`, `co_id`). Danwin's tagger returns `{chunk_id, cos, confidence}`.

### Question
`id`, `module_id`, `co_id` (exactly one CO per question), `stem`, `options` (jsonb, 4 items), `correct_option` (index 0 to 3), `explanation`, `marks` (default 1), `difficulty`, `bloom_level` (nullable), `status` (`draft` | `approved` | `rejected`), `source` (`AI` | `faculty`), `created_by`

Check constraint: `correct_option` between 0 and 3. Grading splits marks by `co_id`.

### Flashcard
`id`, `module_id`, `co_id`, `front`, `back`

### Note
`id`, `module_id`, `co_id` (nullable), `title`, `body`

Flashcards and Notes are generated once per module, never per student.

### Student
`id`, `usn` (unique), `name`, `pin_hash`

### Enrollment
`id`, `student_id`, `subject_id`, `section`

Unique on (`student_id`, `subject_id`). USN is unique per enrollment.

### Quiz
`id`, `module_id`, `subject_id`, `title`, `opens_at`, `closes_at`, `published` (bool), `published_at`, `created_by`

### QuizQuestion (join table)
`quiz_id`, `question_id`, `position`

The database must refuse a published quiz containing a question that is not approved.

### QuizAttempt
`id`, `quiz_id`, `student_id`, `attempt_number` (1 or 2), `answers` (jsonb: question_id to chosen option), `total_score`, `max_score`, `started_at`, `submitted_at`

Unique on (`quiz_id`, `student_id`, `attempt_number`). Check constraint: `attempt_number` in (1, 2).

### StudentCOScore
`id`, `student_id`, `subject_id`, `module_id`, `co_id`, `marks_obtained`, `max_marks`, `percentage`, `attempt_id` (source attempt), `counted` (bool: whether this row counts under `ATTEMPT_RULE`)

Unique on (`student_id`, `module_id`, `co_id`, `attempt_id`). Arya's grading writes these rows. Keeping one row per attempt plus a `counted` flag lets the best, latest or average rule change without losing data.

### Event
`id`, `subject_id`, `section` (nullable), `type` (`quiz` | `assignment` | `exam` | `teaching` | `custom`), `title`, `starts_at`, `ends_at` (nullable), `quiz_id` (nullable), `module_id` (nullable), `created_by` (user id), `created_by_agent` (bool)

### StudyPlan
`id`, `student_id`, `subject_id`, `weak_co_ids` (array), `plan` (jsonb: steps with linked chunk ids and flashcard ids), `generated_at`

Not in the original schema list, but Arya's task 9 says to store the plan with its linked slides and flashcards, so it needs a home.

### AgentLog
`id`, `user_id`, `role`, `kind` (`ai_call` | `tool_call`), `step` (`tagging` | `generation` | `agent` | `qa` | `study_plan` | `flashcards`), `model`, `tool_name` (nullable), `prompt_tokens`, `completion_tokens`, `total_tokens`, `latency_ms`, `args` (jsonb), `result_summary`, `error` (nullable)

Danwin's cost page reads totals per `step`, so `step` and the token columns are the important ones.

## B. Endpoints Arya builds (Aparna: please put these in the contract)

All endpoints take the auth header from the contract and use the standard error format. Faculty-only unless stated.

### Upload pipeline
| Method and path | Purpose | Request | Response |
| --- | --- | --- | --- |
| `POST /modules/{module_id}/upload` | Upload a PPT and start parsing, chunking and tagging | multipart file | `{module_id, processing_status}` |
| `GET /modules/{module_id}/status` | Poll processing progress | none | `{processing_status, chunks_total, chunks_tagged, chunks_untagged, error}` |
| `GET /subjects/{subject_id}/coverage` | Chunks per CO, warning when zero | none | `[{co_id, co_number, chunk_count, warning}]` |

### Quizzes and attempts
| Method and path | Purpose | Request | Response |
| --- | --- | --- | --- |
| `POST /quizzes` | Create a quiz from approved questions | `{module_id, title, question_ids, opens_at, closes_at}` | quiz |
| `POST /quizzes/{id}/publish` | Publish; refuses unapproved questions. Can auto-create the calendar event | none | quiz, plus `event_id` |
| `GET /quizzes?subject_id=` | List quizzes (students see published only) | query | `[quiz]` |
| `POST /quizzes/{id}/attempts` | Start an attempt (max 2). Student only | none | `{attempt_id, attempt_number, attempts_left, questions}` (questions without correct answers) |
| `PUT /attempts/{id}/answers` | Save answers so a refresh keeps them. Student only | `{answers}` | `{saved: true}` |
| `POST /attempts/{id}/submit` | Submit and grade in code. Student only | `{answers}` | `{total_score, max_score, co_scores: [{co_number, marks, max, percentage}]}` |
| `GET /attempts/{id}/review` | Wrong answers with CO and explanation. Student only, own attempts | none | `[{question, chosen, correct, co_number, explanation}]` |

Error cases to define: third attempt returns a clear error code, a closed or unpublished quiz returns a clear error code.

### CO sheet and analytics
| Method and path | Purpose | Request | Response |
| --- | --- | --- | --- |
| `GET /subjects/{id}/co-sheet?scope=module\|semester&module_id=&section=` | Student x CO x total, sorted by USN | query | `{columns: [co_numbers], rows: [{usn, name, co_scores, total}]}` |
| `GET /subjects/{id}/co-summary?section=` | Average per CO, counts above and below threshold, target met | query | `[{co_number, average, above, below, attainment_pct, target_pct, met}]` |
| `GET /subjects/{id}/cos/{co_id}/drilldown` | Modules, questions and students behind one CO | none | `{modules, questions, students}` |
| `GET /subjects/{id}/weak-cos?section=` | COs below target (used by `find_weak_COs`) | query | `[{co_number, attainment_pct, target_pct, gap}]` |
| `GET /subjects/{id}/co-sheet/export?scope=&module_id=&section=` | Excel export, matches the on-screen sheet | query | `.xlsx` file |
| `GET /students/{usn}/progress` | One student's CO scores and quiz history. Student can only request own USN | none | `{usn, co_scores, attempts}` |

### Study features
| Method and path | Purpose | Request | Response |
| --- | --- | --- | --- |
| `POST /qa` | Slide-grounded answer with citations; refuses when nothing matches | `{subject_id, question}` | `{answer, citations: [{module_id, slide_number}], refused}` |
| `GET /retrieve?subject_id=&q=` | Top chunks with slide numbers (internal, used by `/qa`) | query | `[{chunk_id, slide_number, text, score}]` |
| `POST /students/me/study-plan` | Build and store a study plan. Student only | `{subject_id}` | study plan |
| `GET /students/me/study-plan?subject_id=` | Latest stored plan | query | study plan |
| `POST /modules/{id}/study-material` | Generate flashcards and notes for a module, once | none | `{flashcards, notes}` |
| `GET /modules/{id}/flashcards` and `GET /modules/{id}/notes` | Read stored material | none | list |

### Calendar
| Method and path | Purpose | Request | Response |
| --- | --- | --- | --- |
| `POST /events` | Create an event. Agent-created events go through confirmation first | event fields | event |
| `GET /events?subject_id=&from=&to=` | List events. Students see only their subjects | query | `[event]` |
| `PATCH /events/{id}` | Move or edit an event | fields | event |
| `DELETE /events/{id}` | Remove an event | none | `{deleted: true}` |

### Usage
| Method and path | Purpose | Request | Response |
| --- | --- | --- | --- |
| `GET /usage/summary?from=&to=` | Totals per step for Danwin's cost page | query | `[{step, calls, prompt_tokens, completion_tokens, total_tokens}]` |

## C. Endpoints Arya needs from Aparna and Danwin

### From Aparna (schema and API owner)
- `POST /auth/login` (student: USN + PIN; faculty separate) and a way to get the current user and role from the session on the server. Arya's endpoints rely on this for every role check.
- Subject, CO and module CRUD, so the pipeline and sheet have real rows to read.
- `POST /subjects/{id}/roster` (CSV upload with a duplicates and bad-rows report).
- Question endpoints: list drafts by module and CO, edit, approve, reject, create manually. Quiz publish needs question status to be reliable.
- A shared DB access layer or session helper, so everyone queries the same way. Please say which library: SQLAlchemy, supabase-py, or raw asyncpg.
- The standard error format, so Arya's endpoints return errors the same way.

### From Danwin (AI owner)
- `tag_content_with_COs(chunks, cos)` returning `{chunk_id, cos, confidence}` and token usage per call, with the schema committed to `ai/schemas/` before the upload pipeline is built.
- The Token Factory client and prompts that Q&A, study plan and flashcards use. Needed: a chat call that returns text plus token usage, and a JSON-mode call that validates against a schema.
- `generate_quiz(module, co, difficulty, count)` for the seed data.
- Tool JSON schemas for `answer_from_course_material`, `build_study_plan`, `schedule_event` and `list_events`.
- The retrieval decision (see `docs/decisions.md`).

## D. Questions for Aparna

1. Which database library does the backend use (SQLAlchemy, supabase-py or asyncpg)?
2. Are migrations kept as SQL files in `backend/migrations/` or created in the Supabase dashboard? Arya's seed script needs a fixed schema to target.
3. Do you agree with one `StudentCOScore` row per attempt plus a `counted` flag?
4. Are section names free text on Enrollment, or a separate table?
5. How are quiz questions delivered to students without leaking `correct_option`? Arya's start-attempt endpoint strips it; please confirm the question endpoints do the same for students.
