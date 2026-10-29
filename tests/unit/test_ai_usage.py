from ai.usage import make_ai_usage_recorder, make_tool_usage_recorder
from app.services.usage import InMemoryUsageStore


def test_ai_usage_adapter_maps_token_factory_usage_into_existing_usage_service():
    store = InMemoryUsageStore()
    record = make_ai_usage_recorder(store, user_id="fac-1", role="faculty")

    record({
        "step": "co_tagging",
        "model": "nano-test",
        "prompt_tokens": 12,
        "completion_tokens": 4,
        "total_tokens": 16,
        "batch_number": 2,
        "attempt": 1,
    })

    entry = store.entries[0]
    assert entry.step == "tagging"
    assert entry.model == "nano-test"
    assert entry.prompt_tokens == 12
    assert entry.completion_tokens == 4
    assert entry.total_tokens == 16
    assert entry.args == {"batch_number": 2, "attempt": 1}
    assert entry.user_id == "fac-1"


def test_missing_token_counts_are_logged_as_zero_with_error_metadata():
    store = InMemoryUsageStore()
    record = make_ai_usage_recorder(store, user_id="fac-1", role="faculty")

    record({"step": "agent", "model": "agent-test", "error": "TimeoutException"})

    assert store.entries[0].total_tokens == 0
    assert store.entries[0].error == "TimeoutException"


def test_tool_usage_adapter_records_tool_name_without_token_cost():
    store = InMemoryUsageStore()
    record = make_tool_usage_recorder(store, user_id="student-1", role="student")

    record({"tool_name": "get_my_progress", "status": "ok", "latency_ms": 8})

    assert store.entries[0].kind == "tool_call"
    assert store.entries[0].tool_name == "get_my_progress"
    assert store.entries[0].total_tokens == 0
    assert store.entries[0].result_summary == "ok"
