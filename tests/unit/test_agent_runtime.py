from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai.config import AIConfigurationError

def test_agent_runtime_installs_only_registered_faculty_tools(monkeypatch):
    from backend.app import agent_tools
    from backend.app.services.agent_runtime import build_agent_tool_registry, configure_agent_runtime

    calls = []
    monkeypatch.setattr(
        agent_tools,
        "generate_quiz",
        lambda args, user, conn: calls.append((args, user, conn)) or ["q-1", "q-2"],
    )

    class FakeClient:
        def chat(self, **kwargs):
            raise AssertionError("the runtime registry test must not call a live model")

    class Config:
        client = FakeClient()

        def model_for(self, task):
            return {"agent": "agent-test", "generation": "generation-test"}[task]

        def create_client(self):
            return self.client

    app = SimpleNamespace(state=SimpleNamespace())
    assert configure_agent_runtime(app, config=Config()) is True
    connection = object()
    handler = app.state.agent_handler_factory(connection)
    assert [tool.name for tool in handler.loop.tools.for_role("faculty")] == ["generate_quiz"]
    assert handler.loop.tools.for_role("student") == []

    tool = handler.loop.tools.get("generate_quiz")
    result = tool.handler(
        {"module_id": "module-1", "co_id": "co-1", "difficulty": "easy", "count": 2},
        {"user_id": "faculty-1", "role": "faculty"},
    )
    assert result == {"drafts": [{"question_ids": ["q-1", "q-2"], "question_count": 2}]}
    args, user, conn = calls[0]
    assert args.module_id == "module-1"
    assert user["user_id"] == "faculty-1"
    assert conn is connection


def test_agent_runtime_does_not_install_factory_when_model_configuration_is_missing():
    from backend.app.services.agent_runtime import configure_agent_runtime

    class MissingConfig:
        def model_for(self, task):
            raise AIConfigurationError("Missing model configuration")

        def create_client(self):
            raise AssertionError("client should not be created without model config")

    app = SimpleNamespace(state=SimpleNamespace())
    assert configure_agent_runtime(app, config=MissingConfig()) is False
    assert not hasattr(app.state, "agent_handler_factory")
