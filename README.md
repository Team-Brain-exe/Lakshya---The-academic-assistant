# Academic Assistant & CO Tracker

An academic assistant for faculty and students. Faculty upload slides; the system maps content to Course Outcomes (COs), generates quizzes for faculty to approve, grades attempts in code, and tracks CO attainment for every student. An agent on top works through tools over the same data.

**Track:** Best Apps and Agents (NVIDIA x Nebius hackathon)

> Status: skeleton. Sections marked TODO are filled in as each part is built.

## Core ideas

1. **AI runs once per module upload, not once per student.** Cost scales with modules, not class size.
2. **Grading and CO math are plain code.** No LLM ever computes a mark.
3. **AI generates, humans approve.** No generated question reaches a student before faculty approval.
4. **The agent works through tools** over structured data and is role-scoped: a student's agent only reads that student's data.

## How we use NVIDIA Nemotron, Token Factory and Nebius

TODO (Danwin: AI section). Fill in as we build.

| Task | Model | Where it runs |
| --- | --- | --- |
| CO tagging of slide chunks | Nemotron Nano (confirm after model test) | Nebius Token Factory |
| Question, flashcard and note generation | Nemotron Super (confirm) | Nebius Token Factory |
| Agent chat and tool calling | Nemotron Super (confirm) | Nebius Token Factory |
| Hard reasoning, used sparingly | Nemotron Ultra (confirm) | Nebius Token Factory |
| Grading, CO marks, attainment, sheets | No AI | Backend code |

Other Nebius services used: TODO (hosting, Serverless Jobs / Endpoints if adopted).

## Repository layout

```
backend/   FastAPI app: API, auth, grading, CO math, tools
frontend/  React + Tailwind app
ai/        Token Factory client, prompts, tool schemas (ai/schemas/)
notes/     Working notes, including feedback-log.md for the submission form
docs/      API contract, decisions, team plan
seed/      Synthetic demo data (fake USNs only)
tests/     Unit tests and tests/integration smoke test
```

## Setup

Prerequisites: Python 3.11+, Node 18+, a Supabase project, a Token Factory API key.

```bash
git clone <repo-url>
cd academic-assistant
cp .env.example .env        # fill in values; never commit .env
```

Backend (TODO: exact commands once `backend/` exists):

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

## How grading works (TODO: Aparna / Arya)

- Each question belongs to exactly one CO.
- Marks are computed in backend code by comparing answers with the stored correct option, then split by CO.
- Which attempt counts (best, latest or average) is set by `ATTEMPT_RULE`. Default is `best` until faculty confirm.
- The LLM never computes or changes a mark.

## Demo data

All demo data is synthetic. Student seat numbers (USNs) are fake. No real student records are in this repository.

## Hosted demo

TODO: URL (owner: Aparna).

## License

MIT, see [LICENSE](LICENSE).
