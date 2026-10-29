from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from ai.token_factory import TokenFactoryClient, TokenFactoryError
from ai.tagging import tag_content_with_COs
from ai.quiz_generation import generate_quiz, QuizGenerationError


class FakeClient:
    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = []

    def chat(self, *, model, messages, tools=None, tool_choice=None, **kwargs):
        self.calls.append({"model": model, "messages": messages, "tools": tools, **kwargs})
        value = self.contents.pop(0)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(content=value, tool_calls=[], usage={"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10})


def test_token_factory_client_sends_openai_compatible_request_and_returns_usage():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "hello", "tool_calls": []}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
        })

    client = TokenFactoryClient(
        api_key="x",
        base_url="https://factory.example/v1",
        transport=httpx.MockTransport(handler),
    )
    result = client.chat(model="test-model", messages=[{"role": "user", "content": "hi"}])

    assert result.content == "hello"
    assert result.usage == {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}
    assert seen["url"] == "https://factory.example/v1/chat/completions"
    assert seen["authorization"] == "Bearer x"
    assert seen["body"]["model"] == "test-model"


def test_token_factory_rejects_https_url_with_embedded_credentials():
    with pytest.raises(ValueError, match="HTTPS URL"):
        TokenFactoryClient(
            api_key="x",
            base_url="https://user:password@factory.example/v1",
        )


def test_tagging_batches_chunks_and_records_usage():
    chunks = [
        {"id": "a", "text": "Sorting algorithms"},
        {"id": "b", "text": "Binary search"},
        {"id": "c", "text": "Graph traversal"},
    ]
    client = FakeClient([
        '{"tags":[{"chunk_id":"a","cos":[1],"confidence":0.9},{"chunk_id":"b","cos":[2],"confidence":0.8}]}',
        '{"tags":[{"chunk_id":"c","cos":[1,2],"confidence":0.7}]}',
    ])
    usage = []

    result = tag_content_with_COs(
        chunks,
        [{"number": 1, "description": "Algorithms"}, {"number": 2, "description": "Searching"}],
        client,
        model="nano-test",
        batch_size=2,
        usage_recorder=usage.append,
    )

    assert result == [
        {"chunk_id": "a", "cos": [1], "confidence": 0.9},
        {"chunk_id": "b", "cos": [2], "confidence": 0.8},
        {"chunk_id": "c", "cos": [1, 2], "confidence": 0.7},
    ]
    assert len(client.calls) == 2
    assert len(usage) == 2
    assert all(item["model"] == "nano-test" for item in usage)


def test_tagging_retries_bad_json_once_then_leaves_chunk_untagged():
    client = FakeClient(["not json", "still not json"])
    usage = []

    result = tag_content_with_COs(
        [{"id": "a", "text": "Topic"}],
        [{"number": 1, "description": "CO 1"}],
        client,
        model="nano-test",
        usage_recorder=usage.append,
    )

    assert result == []
    assert len(client.calls) == 2
    assert len(usage) == 2
    assert all(entry["total_tokens"] == 10 for entry in usage)
    assert all(entry["error"] for entry in usage)


def test_quiz_generation_returns_unapproved_ai_drafts_for_requested_co():
    client = FakeClient([json.dumps({"questions": [{
        "stem": "Which algorithm sorts in O(n log n)?",
        "options": ["Merge sort", "Linear search", "BFS", "Hash lookup"],
        "correct_option": 0,
        "co_number": 2,
        "explanation": "Merge sort has O(n log n) time.",
        "difficulty": "medium",
    }]})])

    result = generate_quiz(
        {"id": "module-1", "title": "Algorithms"},
        {"id": "co-2", "number": 2, "description": "Analyze algorithms"},
        "medium",
        1,
        client,
        model="super-test",
    )

    assert len(result) == 1
    assert result[0]["module_id"] == "module-1"
    assert result[0]["co_id"] == "co-2"
    assert result[0]["co_number"] == 2
    assert result[0]["status"] == "draft"
    assert result[0]["source"] == "AI"
    assert result[0]["correct_option"] == 0


def test_quiz_generation_rejects_duplicate_stems():
    question = {
        "stem": "Same stem?", "options": ["A", "B", "C", "D"],
        "correct_option": 1, "co_number": 2,
    }
    client = FakeClient([json.dumps({"questions": [question, question]})])

    with pytest.raises(QuizGenerationError, match="duplicate"):
        generate_quiz(
            {"id": "module-1"}, {"id": "co-2", "number": 2}, "easy", 2,
            client, model="super-test",
        )


@pytest.mark.parametrize("reported_difficulty", ["hard", ["medium"], {"level": "medium"}])
def test_quiz_generation_rejects_invalid_or_mismatched_difficulty(reported_difficulty):
    client = FakeClient([json.dumps({"questions": [{
        "stem": "What is a stable sorting algorithm?",
        "options": ["Merge sort", "Quick sort", "Heap sort", "Selection sort"],
        "correct_option": 0,
        "co_number": 2,
        "difficulty": reported_difficulty,
    }]})])

    with pytest.raises(QuizGenerationError, match="difficulty"):
        generate_quiz(
            {"id": "module-1"}, {"id": "co-2", "number": 2}, "medium", 1,
            client, model="super-test",
        )


def test_token_factory_client_rejects_non_object_message():
    client = TokenFactoryClient(
        api_key="x",
        base_url="https://factory.example/v1",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"choices": [{"message": "malformed"}]})
        ),
    )

    with pytest.raises(TokenFactoryError, match="unexpected shape"):
        client.chat(model="test-model", messages=[{"role": "user", "content": "hi"}])
    client.close()


def test_token_factory_client_rejects_plaintext_http_base_url():
    with pytest.raises(ValueError, match="HTTPS"):
        TokenFactoryClient(api_key="x", base_url="http://factory.example/v1")


def test_quiz_schema_matches_runtime_marks_and_option_validation():
    schema_path = Path(__file__).resolve().parents[2] / "ai" / "schemas" / "quiz-drafts.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    question = schema["properties"]["questions"]["items"]["properties"]

    assert question["marks"]["type"] == "number"
    assert question["options"]["uniqueItems"] is True
