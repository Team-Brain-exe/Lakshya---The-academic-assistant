# AI package

The package currently contains the Token Factory HTTP client, CO tagging, quiz draft generation, and JSON contracts. It uses the OpenAI-compatible Chat Completions API; set `TOKEN_FACTORY_BASE_URL` to the exact HTTPS base URL shown in your Token Factory account. The client rejects non-HTTPS URLs so the API key is not sent over plaintext HTTP. No API key is committed.

## Configure

Copy the repository's `.env.example` to `.env` and set:

```dotenv
TOKEN_FACTORY_API_KEY=...
TOKEN_FACTORY_BASE_URL=...
MODEL_TAGGING=...
MODEL_GENERATION=...
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

## Tests

```bash
python -m pytest tests/unit/test_ai_services.py -q
```

The tests use `httpx.MockTransport` and fake model responses. They do not make paid Token Factory calls.
