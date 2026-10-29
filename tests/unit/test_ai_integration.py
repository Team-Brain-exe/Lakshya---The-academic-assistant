from __future__ import annotations

import io
import json
from types import SimpleNamespace

from ai.integration import build_question_batch_payload, build_upload_tagger
from app.pipeline.memory_store import InMemoryChunkStore
from app.pipeline.upload import COInfo, process_module_upload
from tests.unit.helpers import build_deck


class DynamicTagClient:
    def __init__(self):
        self.calls = 0

    def chat(self, *, model, messages, **kwargs):
        self.calls += 1
        payload = json.loads(messages[-1]["content"])
        tags = [
            {"chunk_id": chunk["chunk_id"], "cos": [1], "confidence": 0.9}
            for chunk in payload["chunks"]
        ]
        return SimpleNamespace(content=json.dumps({"tags": tags}), usage={"prompt_tokens": 5, "completion_tokens": 4, "total_tokens": 9})


class BadJsonClient:
    def __init__(self):
        self.calls = 0

    def chat(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(content="not json", usage={"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3})


def test_ai_tagger_adapts_to_upload_pipeline_and_records_usage():
    store = InMemoryChunkStore()
    client = DynamicTagClient()
    usage = []
    tagger = build_upload_tagger(client, model="nano-test", usage_recorder=usage.append)

    report = process_module_upload(
        "module-1",
        io.BytesIO(build_deck()),
        [COInfo(1, "Analyze algorithms")],
        tagger,
        store,
    )

    assert report.status == "done"
    assert report.tagged == report.chunks_saved
    assert report.untagged == 0
    assert client.calls >= 1
    assert usage and usage[0]["step"] == "co_tagging"


def test_invalid_model_json_does_not_fail_upload_or_lose_chunks():
    store = InMemoryChunkStore()
    client = BadJsonClient()
    usage = []
    tagger = build_upload_tagger(client, model="nano-test", usage_recorder=usage.append)

    report = process_module_upload(
        "module-2",
        io.BytesIO(build_deck()),
        [COInfo(1, "Analyze algorithms")],
        tagger,
        store,
    )

    assert report.status == "done"
    assert report.chunks_saved > 0
    assert report.tagged == 0
    assert report.untagged == report.chunks_saved
    assert client.calls == 2
    assert len(usage) == 2


def test_generated_ai_questions_map_to_batch_endpoint_as_drafts_only():
    drafts = [{
        "module_id": "module-1",
        "co_id": "co-1",
        "co_number": 1,
        "stem": "Which algorithm is stable?",
        "options": ["Merge sort", "Quick sort", "Heap sort", "Selection sort"],
        "correct_option": 0,
        "explanation": "Merge sort is stable.",
        "marks": 1.0,
        "difficulty": "medium",
        "bloom_level": "understand",
        "status": "draft",
        "source": "AI",
    }]

    payload = build_question_batch_payload(drafts)

    assert payload["questions"][0]["module_id"] == "module-1"
    assert payload["questions"][0]["co_id"] == "co-1"
    assert "status" not in payload["questions"][0]
    assert "source" not in payload["questions"][0]


def test_batch_payload_refuses_non_draft_or_non_ai_question():
    draft = {
        "module_id": "module-1", "co_id": "co-1", "stem": "Q", "options": ["A", "B", "C", "D"],
        "correct_option": 0, "status": "approved", "source": "AI",
    }

    try:
        build_question_batch_payload([draft])
    except ValueError as exc:
        assert "draft" in str(exc).lower()
    else:
        raise AssertionError("approved model output must never enter the draft-batch integration")
