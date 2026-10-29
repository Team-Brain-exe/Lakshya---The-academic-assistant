from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from ai.content_generation import (
    build_slide_qa_client,
    build_study_material_generator,
    build_study_plan_generator,
)


class FakeClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=self.content, usage={"prompt_tokens": 8, "completion_tokens": 5, "total_tokens": 13})


def test_slide_qa_adapter_uses_only_retrieved_context_and_logs_usage():
    client = FakeClient("According to Slide 2, binary search needs sorted input.")
    usage = []
    answer = build_slide_qa_client(client, model="agent-test", usage_recorder=usage.append)

    result = answer("What does binary search require?", "[Slide 2]: Binary search requires sorted input.")

    assert "sorted input" in result
    assert "untrusted" in client.calls[0]["messages"][0]["content"].lower()
    assert usage[0]["step"] == "qa"
    assert usage[0]["total_tokens"] == 13


def test_study_plan_adapter_rejects_hallucinated_slide_citations():
    payload = {"steps": [{
        "co_number": 1,
        "goal": "Master CO1",
        "recommendation": "Review the material",
        "slides": [{"module_id": "m1", "slide_number": 99}],
        "flashcards": [],
    }]}
    generator = build_study_plan_generator(FakeClient(json.dumps(payload)), model="super-test")

    with pytest.raises(ValueError, match="slide"):
        generator(
            [1],
            [{"module_id": "m1", "slide_number": 2, "co_number": 1, "text": "Sorting"}],
            [],
        )


def test_study_material_adapter_returns_valid_flashcards_and_notes():
    payload = {
        "flashcards": [{"co_id": "co1", "front": "What is sorting?", "back": "Ordering items."}],
        "notes": [{"co_id": "co1", "title": "Sorting", "body": "Sorting orders items."}],
    }
    client = FakeClient(json.dumps(payload))
    usage = []
    generator = build_study_material_generator(
        client,
        model="super-test",
        usage_recorder=usage.append,
    )

    cards, notes = generator("Sorting", [{"co_id": "co1", "slide_number": 1, "text": "Sorting orders items."}])

    assert cards[0]["front"] == "What is sorting?"
    assert notes[0]["title"] == "Sorting"
    assert usage[0]["step"] == "flashcards"
