# Academic Assistant & CO Tracker

An academic assistant for faculty and students. Faculty upload slides; the system maps content to Course Outcomes (COs), generates quizzes for faculty to approve, grades attempts in code, and tracks CO attainment for every student. An agent on top works through tools over the same data.

**Track:** Best Apps and Agents (NVIDIA x Nebius hackathon)

> Status: skeleton. Sections marked TODO are filled in as each part is built.

## Core ideas

1. **AI runs once per module upload, not once per student.** Cost scales with modules, not class size.
2. **Grading and CO math are plain code.** No LLM ever computes a mark.
3. **AI generates, humans approve.** No generated question reaches a student before faculty approval.
4. **The agent works through tools** over structured data and is role-scoped: a student's agent only reads that student's data.

## Repository layout

```
backend/   FastAPI app: API, auth, grading, CO math, agent tools
frontend/  React + Tailwind app
ai/        Token Factory client, prompts, tool schemas (ai/schemas/)
notes/     Working notes, feedback-log.md
docs/      API contract, decisions, team plan
seed/      Synthetic demo data (fake USNs only)
tests/     Unit tests (pytest)
Dockerfile Docker image for the backend
render.yaml Render Blueprint definition
```

## Setup

Prerequisites: Python 3.12+, Node 18+, a Supabase Postgres project.

```bash
git clone <repo-url>
cd academic-assistant
cp .env.example .env        # fill in values; never commit .env
```

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend (TODO):

```bash
cd frontend
npm install
npm run dev
```

Seed demo data (TODO):

```bash
python seed/seed.py
```

## Backend

### How grading works (plain code, never an LLM)

All of this lives in `backend/app/engine/` — pure Python, no LLM calls:

- **`grading.py`** — Each question belongs to exactly one CO. An attempt is graded by comparing each answer with the stored `correct_option` and summing the question's marks. The marks are then split by CO.
- **`co_math.py`** — Aggregation, attempt-rule selection, CO sheet, class summary, weak-CO detection, and drill-down.

Rules:
- A question left blank or answered with an invalid option earns 0 but still counts toward the maximum (it was shown to the student).
- A CO with no questions in scope is "no data" (`None`). Never 0, never included in averages.
- A student's CO score = `sum(obtained) / sum(maximum) × 100` over the counted quizzes in scope.
- `ATTEMPT_RULE` decides which attempt counts: `best` (highest total, tie → later attempt), `latest`, or `average`. Default is `best` until faculty confirm.
- Class attainment for a CO = share of enrolled students at or above the CO threshold. A CO is "weak" when attainment is below its target.

### What the LLM never does

| LLM does | LLM never does |
|---|---|
| Tag slide chunks to COs | Compute a student's marks |
| Generate question stems / options | Approve a question (faculty only) |
| Write study plan text | Choose the user identity (from token) |
| Draft agent replies | Bypass RLS or access-control checks |
| | Insert quiz_attempts or student_co_scores rows |

### Database schema and constraints

The schema is in `backend/migrations/001_init.sql` (PostgreSQL / Supabase).
Key tables: `students`, `users`, `subjects`, `course_outcomes`, `modules`,
`content_chunks`, `questions`, `enrollments`, `quizzes`, `quiz_questions`,
`quiz_attempts`, `student_co_scores`, `events`, `study_plans`, `agent_logs`.

Key constraints enforced by the database:
- **USN normalisation** — `CHECK (usn = upper(btrim(usn)))`; the app uppercases + trims before insert.
- **2 attempts max** — `quiz_attempts.attempt_number CHECK (attempt_number IN (1, 2))`.
- **4 options, one correct** — `CHECK (jsonb_array_length(options) = 4)` and `CHECK (correct_option BETWEEN 0 AND 3)`.
- **Question status** — `CHECK (status IN ('draft', 'approved', 'rejected'))`.
- **Approval triggers** (3 triggers in migration 001):
  1. Unapproved questions cannot be added to a quiz (`fn_quiz_question_must_be_approved`).
  2. A quiz cannot be published with unapproved or no questions (`fn_quiz_publish_check`).
  3. An approved question cannot be un-approved while it is in a published quiz (`fn_question_unapprove_guard`).
- **Enrollment uniqueness** — `UNIQUE (student_id, subject_id)`.
- **Score bounds** — `marks_obtained >= 0`, `max_marks > 0`, `percentage BETWEEN 0 AND 100`, `marks_obtained <= max_marks`.

### RLS lock-down

Supabase exposes tables over REST (PostgREST). Migrations 002 and 004 lock this down:

- **Migration 002** (`002_lock_down_api.sql`): Enables RLS on every existing table in `public`, then revokes all privileges from `anon` and `authenticated` roles.
- **Migration 004** (`004_default_privileges.sql`): Alters default privileges for the `postgres` and `supabase_admin` roles so that any **new** table, sequence, or function created in `public` does not automatically grant access to `anon` or `authenticated`.

**Rule: every new table added to `public` must also run `ALTER TABLE public.<new_table> ENABLE ROW LEVEL SECURITY;`** — either in a migration or by re-running migration 002.

The backend itself connects as the `postgres` role and bypasses RLS. All application-level access control (faculty vs. student, own data only) is enforced in FastAPI code.

### Applying migrations

```bash
cd /path/to/project
python backend/migrations/apply.py
```

This runs every `.sql` file in `backend/migrations/` in alphabetical order, each in its own transaction. Files are idempotent.

### Running tests

```bash
# from project root with .venv active
pytest                # runs all tests under tests/
pytest tests/backend/test_agent_tools.py -v   # just the agent tools tests
pytest tests/backend/test_quizzes.py -v      # just the quiz tests
```

`pytest.ini` points at `backend/` (via `pythonpath`) and `tests/`, so no
extra setup is needed beyond `.env`.

### Deployment (Render)

**Hosting choice:** Backend on Render free tier. DB stays on Supabase (Postgres).
The backend connects directly to Supabase Postgres via `DATABASE_URL`.

A `Dockerfile` and `render.yaml` are provided in the repo root.

**Single-worker requirement:** The login rate limiter
(`backend/app/deps.py`, `LoginRateLimiter`) is in-memory. With multiple workers
a student could bypass the limit by hitting a different worker. The Dockerfile
and `render.yaml` start uvicorn with `--workers 1`. Replace the limiter with
Redis or a DB-backed store before scaling to multiple workers.

#### Deploy steps on Render

1. Push a branch to GitHub (or any git provider linked to Render).
2. In the Render dashboard: **New** → **Web Service** → connect your repo.
3. When Render detects `render.yaml`, click **Edit** next to the service
   and set the runtime to **Docker**.
4. Click **Create web service**. Render will start building the image.
5. Before the service can start, add secrets (see below).

#### Setting secrets on the Render dashboard

1. In the Render dashboard, open your service.
2. Go to the **Environment** tab.
3. Under **Secrets**, click **Add Secret**.
4. Create each secret with these exact key names:

| Secret name | Value | Example |
|---|---|---|
| `DATABASE_URL` | Supabase connection string | `postgresql://postgres.[password]@[host]:5432/postgres` |
| `SESSION_SECRET` | Random string for JWT signing — generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"` | — |
| `FRONTEND_ORIGIN` | Your frontend URL | `http://localhost:5173` (dev) or `https://app.example.com` (prod) |

5. After adding all three secrets, the service auto-redeploys.
6. Watch the **Deploys** tab; the build should succeed and the health check at
   `/health` should return `{"status":"ok"}`.

#### Local Docker build

```bash
docker build -t academic-assistant .
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+psycopg://..." \
  -e SESSION_SECRET="..." \
  -e FRONTEND_ORIGIN="http://localhost:5173" \
  academic-assistant
```

## Running the tests

```bash
pip install -r backend/requirements.txt
pytest
```

`pytest.ini` points at `backend/` and `tests/`, so no other setup is needed.

## Demo data

All demo data is synthetic. Student seat numbers (USNs) are fake. No real student records are in this repository.

## Hosted demo

TODO: URL (owner: Aparna).

## License

MIT, see [LICENSE](LICENSE).
