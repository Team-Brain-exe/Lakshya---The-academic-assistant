# API contract

Owner: Aparna. Version 0.1, Oct 19. Everyone codes against this file. If you need a change, edit this file in the same pull request as the code and tell the team.

Endpoint owners are marked **[Aparna]**, **[Arya]** or **[Danwin]**. The owner implements it. Shapes marked **TBC** are the owner's to confirm; reply in this file.

**Implementation note:** The DB layer uses SQLAlchemy Core with raw `text()` queries (no ORM models). Each request opens one connection via `get_conn()` which auto-commits on success and rolls back on error. RLS is enabled on all tables (migration 002); the backend connects as the `postgres` role which bypasses RLS, so all access control is enforced in application code.

**Status legend:**
- `live` — route is registered in `main.py` with a real implementation
- `scaffolded` — router file exists with handler classes, not yet registered in `main.py`, no Postgres-backed store
- `planned` — listed here but not yet implemented

## 1. Conventions

- **Base URL:** `/` on the backend host (no `/api` prefix). Local: `http://localhost:8000`.
- **Format:** JSON in and out, except file uploads (`multipart/form-data`) and the Excel export.
- **IDs:** UUID strings. **Times:** ISO 8601 in UTC, for example `2026-10-23T09:30:00Z`.
- **Field names:** `snake_case`.
- **Database library:** SQLAlchemy 2.0 with psycopg. Migrations are SQL files in `backend/migrations/`.

### Auth header

Every endpoint except `POST /auth/login` needs:

```
Authorization: Bearer ***
```

The token is a JWT (HS256, signed with `SESSION_SECRET`, expires after 8 hours). Claims: `sub` (user id), `role` (`faculty` or `student`), `student_id` and `usn` (students only). Backend code gets the current user from one dependency, `get_current_user()`, which returns `{user_id, role, student_id, usn}`. **Never read the user or role from a request body, query string or model output.**

### Error format

Every error uses this shape and the matching HTTP status:

```json
{ "error": { "code": "ATTEMPT_LIMIT_REACHED", "message": "You have used both attempts for this quiz.", "details": {} } }
```

`details` is optional. Codes:

| HTTP | code | When |
|---|---|---|
| 400 | `BAD_REQUEST` | Malformed request, bad CSV or file |
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired token, or wrong USN/PIN or email/password |
| 403 | `FORBIDDEN` | Valid token, but not allowed (wrong role, or another student's data) |
| 404 | `NOT_FOUND` | Id does not exist, or exists but the caller may not know it exists |
| 409 | `CONFLICT` | Duplicate or state clash (for example a duplicate subject code) |
| 409 | `ATTEMPT_LIMIT_REACHED` | Third attempt on a quiz |
| 409 | `QUIZ_NOT_PUBLISHED` | Quiz is not published |
| 409 | `QUIZ_NOT_OPEN` | Before `opens_at` |
| 409 | `QUIZ_CLOSED` | After `closes_at` |
| 409 | `QUESTION_NOT_APPROVED` | A draft or rejected question was used in a quiz |
| 422 | `VALIDATION_ERROR` | Body or query failed validation; `details` lists the fields |
| 429 | `RATE_LIMITED` | Too many login attempts |
| 500 | `INTERNAL_ERROR` | Anything unexpected; never leak a stack trace |

Database errors from the schema's rules (attempt limit, unapproved question, duplicate USN) must be caught and mapped to the codes above.

### Roles and data rules

- **Faculty** sees and edits only subjects where `subjects.faculty_user_id` is their user id.
- **Student** sees only subjects they are enrolled in, only published quizzes, and only their own attempts, scores, plans and progress.
- A student asking for another student's data gets `403 FORBIDDEN`. Both the REST endpoints and the agent tools follow the same rule.
- **Students never receive `correct_option` or `explanation`** from any endpoint except `GET /attempts/{id}/review` for their own submitted attempt.
- A student token can never call a faculty endpoint (`403`).

## 2. Auth [Aparna]

| Method and path | Role | Request | Response | Status |
|---|---|---|---|---|
| `POST /auth/login` | public | Student: `{"usn": "1AB21CS001", "pin": "483920"}`. Faculty: `{"email": "...", "password": "..."}` | `200 {"access_token", "token_type": "bearer", "role", "user": {"id", "name", "usn"?, "email"?"}}` | live |
| `GET /auth/me` | any | none | `{"id", "role", "name", "usn"?, "email"?, "student_id"?}` | live |

- USN is trimmed and uppercased by the server before lookup.
- Wrong credentials return `401 UNAUTHENTICATED` with the same message for "no such user" and "wrong PIN".
- Login is rate limited per USN/email and per IP. Too many failures return `429 RATE_LIMITED`.
- PINs are 6 digits, hashed with bcrypt.

## 3. Subjects, COs, modules [Aparna]

Faculty only unless stated. Students may call `GET /subjects` and `GET /subjects/{id}`.

| Method and path | Request | Response | Status |
|---|---|---|---|
| `GET /subjects` | none | `[subject]` (faculty: own subjects; student: enrolled subjects) | live |
| `POST /subjects` | `{code, name, semester, target_attainment_pct?, default_threshold_pct?}` | `201 subject` | live |
| `GET /subjects/{id}` | none | `subject` with `cos` and `modules` arrays | live |
| `PATCH /subjects/{id}` | any subject fields | `subject` | live |
| `DELETE /subjects/{id}` | none | `{"deleted": true}` | live |
| `GET /subjects/{id}/cos` | none | `[co]` | live |
| `PUT /subjects/{id}/cos` | `{"cos": [{number, description, threshold_pct?, target_attainment_pct?}]}` (up to 6, `number` 1 to 6; creates or updates by number) | `[co]` | live |
| `GET /subjects/{id}/modules` | none | `[module]` | planned |
| `POST /subjects/{id}/modules` | `{number, title}` | `201 module` | live |
| `PATCH /modules/{id}` | `{number?, title?}` | `module` | live |
| `DELETE /modules/{id}` | none | `{"deleted": true}` | live |

Shapes:

```json
subject: {"id","code","name","semester","target_attainment_pct","default_threshold_pct","faculty_user_id"}
co:      {"id","subject_id","number","description","threshold_pct","target_attainment_pct"}
module:  {"id","subject_id","number","title","ppt_file_path","processing_status","processing_error","processed_at"}
```

## 4. Roster [Aparna]

Faculty only. CSV columns: `usn,name,section`. `pin` is optional; when missing the server generates a 6-digit PIN.

| Method and path | Request | Response | Status |
|---|---|---|---|
| `POST /subjects/{id}/roster/preview` | multipart `file` (CSV). Saves nothing | `{"total_rows", "valid": [{row, usn, name, section}], "bad_rows": [{row, usn, reason}], "duplicates_in_file": [{usn, rows}], "already_enrolled": [usn]}` | live |
| `POST /subjects/{id}/roster` | multipart `file` (the same CSV, after the faculty confirms the preview) | `{"created_students", "created_enrollments", "skipped": [{row, usn, reason}], "credentials": [{usn, pin}]}` | live |

- USNs are trimmed and uppercased before duplicate checks.
- `credentials` lists new students' PINs. It is returned **once** and never stored in plain text. The frontend lets faculty download it.
- An existing student (same USN) is enrolled in the subject without changing their PIN.

## 5. Questions [Aparna]

Faculty only. Status values: `draft`, `approved`, `rejected`. Source: `AI` or `faculty`.

| Method and path | Request | Response | Status |
|---|---|---|---|
| `GET /questions?module_id=&co_id=&status=&source=` | query (`module_id` required) | `[question]` | live |
| `POST /questions` | manual question: `{module_id, co_id, stem, options: [4 strings], correct_option: 0-3, explanation?, marks?, difficulty?, bloom_level?}` | `201 question` (source `faculty`, status `draft`) | live |
| `POST /questions/batch` | `{"questions": [{...same fields..., "source": "AI"}]}` for the `generate_quiz` tool; every item is saved as `draft` | `201 [question]` | live |
| `PATCH /questions/{id}` | any editable field | `question` | live |
| `POST /questions/{id}/approve` | none | `question` (status `approved`) | live |
| `POST /questions/{id}/reject` | none | `question` (status `rejected`) | live |

```json
question: {"id","module_id","co_id","co_number","stem","options":["A","B","C","D"],"correct_option":1,"explanation","marks","difficulty","bloom_level","status","source","created_by"}
```

- Exactly 4 options and `correct_option` between 0 and 3, enforced by the database.
- Faculty-written questions are created as `draft` and approved the same way as AI ones. A question cannot be un-approved while it is in a published quiz (`409 CONFLICT`).

## 6. Upload pipeline [Arya]

Faculty only.

| Method and path | Request | Response | Status |
|---|---|---|---|
| `POST /modules/{module_id}/upload` | multipart `file` (.pptx) | `202 {module_id, processing_status}` | scaffolded |
| `GET /modules/{module_id}/status` | none | `{processing_status, chunks_total, chunks_tagged, chunks_untagged, error}` | scaffolded |
| `GET /subjects/{subject_id}/coverage` | none | `[{co_id, co_number, chunk_count, warning}]` | scaffolded |

`processing_status`: `pending`, `processing`, `done`, `failed`. An untagged chunk never fails the upload.

## 7. Quizzes and attempts [Arya]

| Method and path | Role | Request | Response | Status |
|---|---|---|---|---|
| `POST /quizzes` | faculty | `{module_id, title, question_ids, opens_at, closes_at}` | `201 quiz` | live |
| `GET /quizzes` | faculty | query (`subject_id?`, `module_id?`) | `[quiz]` | live |
| `GET /quizzes` | student | query (`subject_id?`, `module_id?`) | `[quiz]` with `attempts_used` and `attempts_left` | live |
| `POST /quizzes/{id}/questions` | faculty | `{"question_id": "..."}` | `{"added": true, "question_id": "..."}` | live |
| `POST /quizzes/{id}/publish` | faculty | none | `quiz` plus `event_id`. Refuses unapproved questions with `QUESTION_NOT_APPROVED` | live |
| `GET /quizzes/{id}` | faculty | none | `quiz` | live |
| `GET /quizzes/{id}` | student | none | `quiz` only if published and enrolled; else `404` | live |
| `POST /quizzes/{id}/attempts` | student | none | `201 {attempt_id, attempt_number, attempts_left, questions}`; `questions` never includes `correct_option` or `explanation` | planned |
| `GET /attempts/{id}` | student (own) | none | `{attempt_id, quiz_id, attempt_number, attempts_left, status, answers, questions, closes_at}`; used to resume after a refresh | planned |
| `PUT /attempts/{id}/answers` | student (own) | `{"answers": {"<question_id>": <option_index>}}` | `{"saved": true}` | planned |
| `POST /attempts/{id}/submit` | student (own) | `{"answers": {...}}` | `{total_score, max_score, co_scores: [{co_number, marks, max, percentage}]}` | planned |
| `GET /attempts/{id}/review` | student (own, submitted) | none | `[{question, chosen, correct, co_number, explanation}]` | planned |

```json
quiz: {"id","module_id","subject_id","title","opens_at","closes_at","published","published_at","question_count","attempts_used"?"attempts_left"?}
```

Errors to implement: third attempt returns `ATTEMPT_LIMIT_REACHED`; before opening returns `QUIZ_NOT_OPEN`; after closing returns `QUIZ_CLOSED`; unpublished returns `QUIZ_NOT_PUBLISHED`.

## 8. CO sheet and analytics [Arya]

| Method and path | Role | Response | Status |
|---|---|---|---|
| `GET /subjects/{id}/co-sheet?scope=module\|semester&module_id=&section=` | faculty | `{columns: [co_numbers], rows: [{usn, name, co_scores, total}]}` sorted by USN | scaffolded |
| `GET /subjects/{id}/co-summary?section=` | faculty | `[{co_number, average, above, below, attainment_pct, target_pct, met}]` | scaffolded |
| `GET /subjects/{id}/cos/{co_id}/drilldown` | faculty | `{modules, questions, students}` (inner shapes **TBC** by Arya) | scaffolded |
| `GET /subjects/{id}/weak-cos?section=` | faculty | `[{co_number, attainment_pct, target_pct, gap}]` | scaffolded |
| `GET /subjects/{id}/co-sheet/export?scope=&module_id=&section=` | faculty | `.xlsx` file download | scaffolded |
| `GET /students/me/progress?subject_id=` | student | `{usn, co_scores: [{co_number, percentage, threshold_pct}], attempts: [...]}` | scaffolded |
| `GET /students/{usn}/progress?subject_id=` | faculty, or the student for their own USN only | same shape. Another student's USN returns `403 FORBIDDEN` | scaffolded |

## 9. Study features [Arya]

| Method and path | Role | Request | Response | Status |
|---|---|---|---|---|
| `POST /qa` | student | `{subject_id, question}` | `{answer, citations: [{module_id, slide_number}], refused}` | scaffolded |
| `GET /retrieve?subject_id=&q=` | internal | query | `[{chunk_id, slide_number, text, score}]` | scaffolded |
| `POST /students/me/study-plan` | student | `{subject_id}` | study plan (shape **TBC** by Arya) | scaffolded |
| `GET /students/me/study-plan?subject_id=` | student | query | latest stored plan | scaffolded |
| `POST /modules/{id}/study-material` | faculty | none | `{flashcards, notes}` | scaffolded |
| `GET /modules/{id}/flashcards` | both | none | `[{id, co_id, front, back}]` | scaffolded |
| `GET /modules/{id}/notes` | both | none | `[{id, co_id, title, body}]` | scaffolded |

## 10. Calendar [Arya]

| Method and path | Role | Request | Response | Status |
|---|---|---|---|---|
| `POST /events` | faculty | `{subject_id, section?, type, title, starts_at, ends_at?, quiz_id?, module_id?}` | `201 event` | scaffolded |
| `GET /events?subject_id=&from=&to=` | both | query | `[event]`; students see only their subjects | scaffolded |
| `PATCH /events/{id}` | faculty | event fields | `event` | scaffolded |
| `DELETE /events/{id}` | faculty | none | `{"deleted": true}` | scaffolded |

`type`: `quiz`, `assignment`, `exam`, `teaching`, `custom`. Events created by the agent are saved only after the user confirms (see section 11).

## 11. Agent [Danwin]

| Method and path | Role | Request | Response | Status |
|---|---|---|---|---|
| `POST /agent/chat` | both | `{"message": "...", "conversation_id"?}` | `{conversation_id, reply, tool_calls: [{name, status}], proposals: [...], drafts: [...]}` (full shape **TBC** by Danwin) | planned |
| `POST /agent/confirm` | both | `{"proposal_id", "approve": true\|false}` | `{status, event?}` | planned |

- `proposals` holds schedule and move actions that are not saved until `/agent/confirm` is called with `approve: true`.
- `drafts` holds generated quizzes with a `review_url` to the faculty review screen.
- The user and role come from the token. Tool arguments cannot choose another student's USN.

### Agent tools owned by Aparna

Implemented as backend functions, called by the agent loop with the session user injected by the server:

| Tool | Role | Notes | Status |
|---|---|---|---|
| `get_co_attainment(subject_id, section?)` | faculty | Wraps `co-summary` | planned |
| `find_weak_COs(subject_id, section?)` | faculty | Wraps `weak-cos` | planned |
| `get_student_progress(usn?)` | both | A student's `usn` argument is ignored and replaced by their own | planned |
| `export_sheet(subject_id, scope?, module_id?)` | faculty | Wraps the export endpoint, returns a download link | planned |
| `generate_quiz(module_id, co_id, difficulty, count)` | faculty | Calls Danwin's generation function, then `POST /questions/batch` as drafts | planned |

Every tool validates its arguments against the JSON schemas in `ai/schemas/` before running.

## 12. Usage [Arya]

| Method and path | Role | Response | Status |
|---|---|---|---|
| `GET /usage/summary?from=&to=` | faculty | `[{step, calls, prompt_tokens, completion_tokens, total_tokens}]` | scaffolded |

## 13. Health

| Method and path | Role | Response | Status |
|---|---|---|---|
| `GET /health` | public | `{"status": "ok"}`; used by the hosting platform and Danwin's smoke test | live |

## Open items

- Arya: confirm the shapes marked TBC (drilldown, study plan).
- Danwin: confirm the `/agent/*` shapes and publish the tool schemas to `ai/schemas/`.
- Faculty: which attempt counts (default `best`), the real threshold and target values, and the university's sheet format.
