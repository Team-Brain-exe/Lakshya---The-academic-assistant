# API contract

Owner: Aparna. Version 0.1, Oct 19. Everyone codes against this file. If you need a change, edit this file in the same pull request as the code and tell the team.

Endpoint owners are marked **[Aparna]**, **[Arya]** or **[Danwin]**. The owner implements it. Shapes marked **TBC** are the owner's to confirm; reply in this file.

## 1. Conventions

- **Base URL:** `/` on the backend host (no `/api` prefix). Local: `http://localhost:8000`.
- **Format:** JSON in and out, except file uploads (`multipart/form-data`) and the Excel export.
- **IDs:** UUID strings. **Times:** ISO 8601 in UTC, for example `2026-10-23T09:30:00Z`.
- **Field names:** `snake_case`.
- **Database library:** SQLAlchemy 2.0 with psycopg. Migrations are SQL files in `backend/migrations/`.

### Auth header

Every endpoint except `POST /auth/login` needs:

```
Authorization: Bearer <access_token>
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

| Method and path | Role | Request | Response |
|---|---|---|---|
| `POST /auth/login` | public | Student: `{"usn": "1AB21CS001", "pin": "483920"}`. Faculty: `{"email": "...", "password": "..."}` | `200 {"access_token", "token_type": "bearer", "role", "user": {"id", "name", "usn"?, "email"?}}` |
| `GET /auth/me` | any | none | `{"id", "role", "name", "usn"?, "email"?, "student_id"?}` |

- USN is trimmed and uppercased by the server before lookup.
- Wrong credentials return `401 UNAUTHENTICATED` with the same message for "no such user" and "wrong PIN".
- Login is rate limited per USN/email and per IP. Too many failures return `429 RATE_LIMITED`.
- PINs are 6 digits, hashed with bcrypt.

## 3. Subjects, COs, modules [Aparna]

Faculty only unless stated. Students may call `GET /subjects` and `GET /subjects/{id}`.

| Method and path | Request | Response |
|---|---|---|
| `GET /subjects` | none | `[subject]` (faculty: own subjects; student: enrolled subjects) |
| `POST /subjects` | `{code, name, semester, target_attainment_pct?, default_threshold_pct?}` | `201 subject` |
| `GET /subjects/{id}` | none | `subject` with `cos` and `modules` arrays |
| `PATCH /subjects/{id}` | any subject fields | `subject` |
| `DELETE /subjects/{id}` | none | `{"deleted": true}` |
| `GET /subjects/{id}/cos` | none | `[co]` |
| `PUT /subjects/{id}/cos` | `{"cos": [{number, description, threshold_pct?, target_attainment_pct?}]}` (up to 6, `number` 1 to 6; creates or updates by number) | `[co]` |
| `GET /subjects/{id}/modules` | none | `[module]` |
| `POST /subjects/{id}/modules` | `{number, title}` | `201 module` |
| `PATCH /modules/{id}` | `{number?, title?}` | `module` |
| `DELETE /modules/{id}` | none | `{"deleted": true}` |

Shapes:

```json
subject: {"id","code","name","semester","target_attainment_pct","default_threshold_pct","faculty_user_id"}
co:      {"id","subject_id","number","description","threshold_pct","target_attainment_pct"}
module:  {"id","subject_id","number","title","ppt_file_path","processing_status","processing_error","processed_at"}
```

## 4. Roster [Aparna]

Faculty only. CSV columns: `usn,name,section`. `pin` is optional; when missing the server generates a 6-digit PIN.

| Method and path | Request | Response |
|---|---|---|
| `POST /subjects/{id}/roster/preview` | multipart `file` (CSV). Saves nothing | `{"total_rows", "valid": [{row, usn, name, section}], "bad_rows": [{row, usn, reason}], "duplicates_in_file": [{usn, rows}], "already_enrolled": [usn]}` |
| `POST /subjects/{id}/roster` | multipart `file` (the same CSV, after the faculty confirms the preview) | `{"created_students", "created_enrollments", "skipped": [{row, usn, reason}], "credentials": [{usn, pin}]}` |

- USNs are trimmed and uppercased before duplicate checks.
- `credentials` lists new students' PINs. It is returned **once** and never stored in plain text. The frontend lets faculty download it.
- An existing student (same USN) is enrolled in the subject without changing their PIN.

## 5. Questions [Aparna]

Faculty only. Status values: `draft`, `approved`, `rejected`. Source: `AI` or `faculty`.

| Method and path | Request | Response |
|---|---|---|
| `GET /questions?module_id=&co_id=&status=&source=` | query (`module_id` required) | `[question]` |
| `POST /questions` | manual question: `{module_id, co_id, stem, options: [4 strings], correct_option: 0-3, explanation?, marks?, difficulty?, bloom_level?}` | `201 question` (source `faculty`, status `draft`) |
| `POST /questions/batch` | `{"questions": [{...same fields..., "source": "AI"}]}` for the `generate_quiz` tool; every item is saved as `draft` | `201 [question]` |
| `PATCH /questions/{id}` | any editable field | `question` |
| `POST /questions/{id}/approve` | none | `question` (status `approved`) |
| `POST /questions/{id}/reject` | none | `question` (status `rejected`) |

```json
question: {"id","module_id","co_id","co_number","stem","options":["A","B","C","D"],"correct_option":1,"explanation","marks","difficulty","bloom_level","status","source","created_by"}
```

- Exactly 4 options and `correct_option` between 0 and 3, enforced by the database.
- Faculty-written questions are created as `draft` and approved the same way as AI ones. A question cannot be un-approved while it is in a published quiz (`409 CONFLICT`).

## 6. Upload pipeline [Arya]

Faculty only.

| Method and path | Request | Response |
|---|---|---|
| `POST /modules/{module_id}/upload` | multipart `file` (.pptx) | `202 {module_id, processing_status}` |
| `GET /modules/{module_id}/status` | none | `{processing_status, chunks_total, chunks_tagged, chunks_untagged, error}` |
| `GET /subjects/{subject_id}/coverage` | none | `[{co_id, co_number, chunk_count, warning}]` |

`processing_status`: `pending`, `processing`, `done`, `failed`. An untagged chunk never fails the upload.

## 7. Quizzes and attempts [Arya]

| Method and path | Role | Request | Response |
|---|---|---|---|
| `POST /quizzes` | faculty | `{module_id, title, question_ids, opens_at, closes_at}` | `201 quiz` |
| `POST /quizzes/{id}/publish` | faculty | none | `quiz` plus `event_id`. Refuses unapproved questions with `QUESTION_NOT_APPROVED` |
| `GET /quizzes?subject_id=` | both | query | `[quiz]`. Students see published quizzes for their subjects only, each with `attempts_used` and `attempts_left` |
| `POST /quizzes/{id}/attempts` | student | none | `201 {attempt_id, attempt_number, attempts_left, questions}`; `questions` never includes `correct_option` or `explanation` |
| `GET /attempts/{id}` | student (own) | none | `{attempt_id, quiz_id, attempt_number, attempts_left, status, answers, questions, closes_at}`; used to resume after a refresh |
| `PUT /attempts/{id}/answers` | student (own) | `{"answers": {"<question_id>": <option_index>}}` | `{"saved": true}` |
| `POST /attempts/{id}/submit` | student (own) | `{"answers": {...}}` | `{total_score, max_score, co_scores: [{co_number, marks, max, percentage}]}` |
| `GET /attempts/{id}/review` | student (own, submitted) | none | `[{question, chosen, correct, co_number, explanation}]` |

```json
quiz: {"id","module_id","subject_id","title","opens_at","closes_at","published","published_at","question_count","attempts_used"?,"attempts_left"?}
```

Errors to implement: third attempt returns `ATTEMPT_LIMIT_REACHED`; before opening returns `QUIZ_NOT_OPEN`; after closing returns `QUIZ_CLOSED`; unpublished returns `QUIZ_NOT_PUBLISHED`.

## 8. CO sheet and analytics [Arya]

| Method and path | Role | Response |
|---|---|---|
| `GET /subjects/{id}/co-sheet?scope=module\|semester&module_id=&section=` | faculty | `{columns: [co_numbers], rows: [{usn, name, co_scores, total}]}` sorted by USN |
| `GET /subjects/{id}/co-summary?section=` | faculty | `[{co_number, average, above, below, attainment_pct, target_pct, met}]` |
| `GET /subjects/{id}/cos/{co_id}/drilldown` | faculty | `{modules, questions, students}` (inner shapes **TBC** by Arya) |
| `GET /subjects/{id}/weak-cos?section=` | faculty | `[{co_number, attainment_pct, target_pct, gap}]` |
| `GET /subjects/{id}/co-sheet/export?scope=&module_id=&section=` | faculty | `.xlsx` file download |
| `GET /students/me/progress?subject_id=` | student | `{usn, co_scores: [{co_number, percentage, threshold_pct}], attempts: [...]}` |
| `GET /students/{usn}/progress?subject_id=` | faculty, or the student for their own USN only | same shape. Another student's USN returns `403 FORBIDDEN` |

## 9. Study features [Arya]

| Method and path | Role | Request | Response |
|---|---|---|---|
| `POST /qa` | student | `{subject_id, question}` | `{answer, citations: [{module_id, slide_number}], refused}` |
| `GET /retrieve?subject_id=&q=` | internal | query | `[{chunk_id, slide_number, text, score}]` |
| `POST /students/me/study-plan` | student | `{subject_id}` | study plan (shape **TBC** by Arya) |
| `GET /students/me/study-plan?subject_id=` | student | query | latest stored plan |
| `POST /modules/{id}/study-material` | faculty | none | `{flashcards, notes}` |
| `GET /modules/{id}/flashcards` | both | none | `[{id, co_id, front, back}]` |
| `GET /modules/{id}/notes` | both | none | `[{id, co_id, title, body}]` |

## 10. Calendar [Arya]

| Method and path | Role | Request | Response |
|---|---|---|---|
| `POST /events` | faculty | `{subject_id, section?, type, title, starts_at, ends_at?, quiz_id?, module_id?}` | `201 event` |
| `GET /events?subject_id=&from=&to=` | both | query | `[event]`; students see only their subjects |
| `PATCH /events/{id}` | faculty | event fields | `event` |
| `DELETE /events/{id}` | faculty | none | `{"deleted": true}` |

`type`: `quiz`, `assignment`, `exam`, `teaching`, `custom`. Events created by the agent are saved only after the user confirms (see section 11).

## 11. Agent [Danwin]

| Method and path | Role | Request | Response |
|---|---|---|---|
| `POST /agent/chat` | both | `{"message": "...", "conversation_id"?}` | `{conversation_id, reply, tool_calls: [{name, status}], proposals: [...], drafts: [...]}` (full shape **TBC** by Danwin) |
| `POST /agent/confirm` | both | `{"proposal_id", "approve": true\|false}` | `{status, event?}` |

- `proposals` holds schedule and move actions that are not saved until `/agent/confirm` is called with `approve: true`.
- `drafts` holds generated quizzes with a `review_url` to the faculty review screen.
- The user and role come from the token. Tool arguments cannot choose another student's USN.

### Agent tools owned by Aparna

Implemented as backend functions, called by the agent loop with the session user injected by the server:

| Tool | Role | Notes |
|---|---|---|
| `get_co_attainment(subject_id, section?)` | faculty | Wraps `co-summary` |
| `find_weak_COs(subject_id, section?)` | faculty | Wraps `weak-cos` |
| `get_student_progress(usn?)` | both | A student's `usn` argument is ignored and replaced by their own |
| `export_sheet(subject_id, scope?, module_id?)` | faculty | Wraps the export endpoint, returns a download link |
| `generate_quiz(module_id, co_id, difficulty, count)` | faculty | Calls Danwin's generation function, then `POST /questions/batch` as drafts |

Every tool validates its arguments against the JSON schemas in `ai/schemas/` before running.

## 12. Usage [Arya]

| Method and path | Role | Response |
|---|---|---|
| `GET /usage/summary?from=&to=` | faculty | `[{step, calls, prompt_tokens, completion_tokens, total_tokens}]` |

## 13. Health

| Method and path | Role | Response |
|---|---|---|
| `GET /health` | public | `{"status": "ok"}`; used by the hosting platform and Danwin's smoke test |

## Open items

- Arya: confirm the shapes marked TBC (drilldown, study plan).
- Danwin: confirm the `/agent/*` shapes and publish the tool schemas to `ai/schemas/`.
- Faculty: which attempt counts (default `best`), the real threshold and target values, and the university's sheet format.
