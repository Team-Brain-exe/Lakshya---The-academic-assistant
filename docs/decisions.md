# Decisions and open questions

Status key: **Open** (needs a decision), **Proposed** (Arya's recommendation, waiting for the owner), **Decided**.

## 1. Retrieval for slide Q&A: pgvector or in-memory (Danwin and Arya, due Oct 19)

**Status: Proposed**

**Recommendation: pgvector in the Supabase Postgres we already use, if Token Factory offers an embedding model. If it does not, use Postgres full-text search with no embeddings.**

Why not in-memory:
- The hosted backend can restart, which wipes an in-memory index. We would have to re-embed every chunk on boot, which spends tokens again and breaks our "AI runs once per module upload" claim.
- Retrieval lives in the same database as the chunks, so there is nothing extra to keep in sync.

Why pgvector:
- Supabase supports it as a standard extension. One extra column on `ContentChunk` (`embedding`) and one similarity query.
- Embeddings are computed once, in the upload pipeline, right after tagging. That keeps the cost story intact.
- The corpus is tiny (one subject, a few modules, a few hundred chunks), so even the simplest index is fast.

**The one thing to check first (Danwin):** does Token Factory serve an embedding model, and which one? I have not verified this and do not want to assume it. If an NVIDIA embedding model is available, use it, because it also adds to the NVIDIA model usage we highlight. If none is available:
- Fallback A: Postgres full-text search (`tsvector`) over `ContentChunk.text`. No embeddings, no extra model, good enough for a small and focused corpus.
- Fallback B: keyword scoring (BM25) in Python, computed from the chunks table on demand.

Decision needed from Danwin today:
- [ ] Embedding model available on Token Factory? Model ID: ____
- [ ] If yes: pgvector. If no: full-text search.

If pgvector is chosen, Aparna adds the `vector` extension and the `embedding` column to the schema (see `requests-to-aparna.md`). Embedding dimension depends on the model, so the schema waits for the model ID.

## 2. Which attempt counts when a student attempts twice

**Status: Open, faculty decide. Default: `best`**

The rule lives in config (`ATTEMPT_RULE` in `.env.example`: `best`, `latest` or `average`). Grading writes one `StudentCOScore` row per attempt with a `counted` flag, so changing the rule never loses data. The README says the default is `best` until faculty confirm.

Ask faculty: which of the three does the department use for CO attainment?

## 3. CO threshold and target attainment

**Status: Open, confirm with faculty**

The brief uses 60% and 60% as examples only. Stored per subject and per CO (Aparna), configurable, no hard-coded default in the math. Ask faculty for the real values.

## 4. CO sheet and Excel format

**Status: Open (Arya)**

Ask faculty for a sample of the sheet the university actually uses. Until then the export is: USN, name, one column per CO, total. Whether program outcomes (PO) are needed also depends on this.

## 5. Hosting and who keeps the demo URL up

**Status: Open (Aparna)**

Free tier or Nebius Serverless Endpoints. Aparna owns the demo URL through judging. The upload pipeline is written as a plain function (Arya's task 3), so moving it to Nebius Serverless Jobs later is possible but optional.

## 6. Submission deadline and team size

**Status: Open (whole team)**

The team files describe three people (Danwin, Aparna, Arya). The deadline is not written down anywhere yet. Everything else in the plan depends on it, so someone should find it today.

## Decided so far

- Track: Best Apps and Agents.
- License: MIT.
- Grading and CO math are plain code, never an LLM.
- Faculty approve every generated question before students see it.
- Maximum 2 attempts per student per quiz.
- Students authenticate with USN and PIN.
- Demo data is synthetic only.
