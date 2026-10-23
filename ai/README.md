# AI package

The package currently contains the Token Factory HTTP client, CO tagging, quiz draft generation, and JSON contracts. It uses the OpenAI-compatible Chat Completions API; set `TOKEN_FACTORY_BASE_URL` to the exact HTTPS base URL shown in your Token Factory account. The client rejects non-HTTPS URLs so the API key is not sent over plaintext HTTP. No API key is committed.

## Configure

Copy the repository's `.env.example` to `.env` and set:

```dotenv
TOKEN_FACTORY_API_KEY=...
TOKEN_FACTORY_BASE_URL=...
MODEL_TAGGING=...
MODEL_GENERATION=...
MODEL_AGENT=...
MODEL_REASONING=...
```

The model IDs are intentionally not hard-coded. Choose them only after testing the models in your Token Factory account.

## CO tagging with the upload pipeline

```python
import os
from functools import partial

from ai.tagging import tag_content_with_COs
from ai.token_factory import TokenFactoryClient
from app.pipeline.upload import process_module_upload

client = TokenFactoryClient(
    api_key=os.environ["TOKEN_FACTORY_API_KEY"],
    base_url=os.environ["TOKEN_FACTORY_BASE_URL"],
)

tagger = partial(
    tag_content_with_COs,
    client=client,
    model=os.environ["MODEL_TAGGING"],
    usage_recorder=record_model_usage,  # your usage-log adapter
)
report = process_module_upload(module_id, uploaded_file, cos, tagger, store)
```

`tag_content_with_COs` accepts the same dictionaries or dataclasses as the upload pipeline. It batches by 20 by default, retries a malformed JSON response once, records usage for each model response, and returns only validated tags. A batch that still fails returns no tags so the upload pipeline marks its chunks untagged instead of failing the upload.

## Generate question drafts

```python
from ai.quiz_generation import generate_quiz

questions = generate_quiz(
    module={"id": module_id, "title": "Algorithms"},
    co={"id": co_id, "number": 2, "description": "Analyze algorithms"},
    difficulty="medium",
    count=5,
    client=client,
    model=os.environ["MODEL_GENERATION"],
    usage_recorder=record_model_usage,
)
# POST these as drafts to the faculty question-review endpoint.
# They are never approved or published by the AI function.
```

The function raises `QuizGenerationError` if the response is malformed, the count is wrong, options are invalid, a question is tagged to the wrong CO, or stems/options repeat. Faculty approval remains a separate action.

## Q&A, study plan, flashcards, and notes adapters

`ai.content_generation` provides callbacks matching Arya's existing service interfaces: `build_slide_qa_client()` returns the `(question, context) -> answer` callback used by `answer_from_course_material`; `build_study_plan_generator()` returns a plan generator that validates every slide/card reference against supplied materials; `build_study_material_generator()` returns the flashcard/note generator. These adapters treat retrieved text as untrusted data, capture token usage, and never invent slide or card IDs.

## Tests

```bash
python -m pytest tests/unit/test_ai_services.py tests/unit/test_agent_loop.py tests/unit/test_content_generation.py -q
```

The tests use `httpx.MockTransport` and fake model responses. They do not make paid Token Factory calls.

## Candidate model evaluation

After setting the Token Factory values in the local `.env`, run the manual evaluation harness with candidate model IDs. No model ID is selected automatically.

```bash
python -m ai.evaluate_models tagging --decks deck-a.pptx deck-b.pptx --cos-file cos.json --repeats 3 --output notes/tagging-eval.json
python -m ai.evaluate_models quiz --module-json module.json --co-json co.json --difficulty medium --count 5 --output notes/quiz-eval.json
python -m ai.evaluate_models tool-calling --model YOUR_SUPER_MODEL_ID --output notes/tool-eval.json
```

The tagging report compares repeated outputs and includes short slide previews for manual semantic review. The quiz report runs structural checks but still requires a faculty member to judge factual correctness and distractor quality. The tool-calling mode uses only synthetic dummy data. Do not use real student records for these tests. No `.env` or slide decks are included in the repository; live evaluations must be run locally with authorized credentials and suitable slides.

## Agent tool contracts

`ai/schemas/agent-tools.json` is the shared contract manifest. `build_tool_registry()` binds only implemented server handlers, so an unimplemented tool is not exposed to a model. Student progress uses `get_my_progress`, which has no `usn` argument; faculty lookup is a separate tool. Schedule and move tools are proposal-only: they do not run a write handler until `/agent/confirm` approves the action. Any FastAPI runtime injects the authenticated user from the session, never from model arguments. The loop is capped at six model steps, six tool calls per request, and three calls in one model response. `main.py` optionally installs the PostgreSQL runtime at startup when the HTTPS Token Factory key/base URL and `MODEL_AGENT`/`MODEL_GENERATION` are configured. It currently binds only faculty `generate_quiz`; that server handler verifies subject ownership and saves drafts only. Analytics, student Q&A/study/calendar handlers and proposal executors remain unavailable and are not exposed. With no role-appropriate tool, the loop returns an honest unavailable message without asking a model to invent an answer. Migration 005 and configured credentials are still required for the routes to run; without them `/agent/chat` and `/agent/confirm` report `503 AGENT_NOT_CONFIGURED`. The deployed app uses the PostgreSQL state store, never the in-memory store.
