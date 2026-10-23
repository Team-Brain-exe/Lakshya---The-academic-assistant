from __future__ import annotations

import json
import os
from types import SimpleNamespace


def test_http_agent_route_uses_token_identity_and_rejects_cross_student_arguments():
    # The route module imports the backend config, but this test overrides the DB
    # dependency and never opens a connection. Values are local test placeholders.
    os.environ.setdefault("DATABASE_URL", "postgresql://unused:unused@127.0.0.1/unused")
    os.environ.setdefault("SESSION_SECRET", "local-unit-test-only")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from ai.agent import AgentLoop, AgentTool, ToolRegistry
    from backend.app.routers.agent import get_agent_handler, get_current_user, router
    from backend.app.services.agent_api import AgentRouterHandler
    from backend.app.services.agent_state import InMemoryAgentStateStore

    class FakeClient:
        def __init__(self):
            self.responses = [
                SimpleNamespace(content=None, tool_calls=[{
                    "id": "tc-1",
                    "type": "function",
                    "function": {"name": "get_my_progress", "arguments": json.dumps({"subject_id": "sub-1", "usn": "OTHER123"})},
                }], usage={}),
                SimpleNamespace(content="I can only access your own progress.", tool_calls=[], usage={}),
            ]

        def chat(self, **kwargs):
            return self.responses.pop(0)

    tool_calls = []
    tool = AgentTool(
        name="get_my_progress",
        description="Get the authenticated student's own progress.",
        parameters={
            "type": "object",
            "properties": {"subject_id": {"type": "string", "minLength": 1}},
            "required": ["subject_id"],
            "additionalProperties": False,
        },
        roles=frozenset({"student"}),
        handler=lambda args, user: tool_calls.append((args, user)) or {"co_scores": []},
    )
    user = {"user_id": "user-1", "role": "student", "student_id": "student-1", "usn": "OWN123"}
    loop = AgentLoop(FakeClient(), model="agent-test", tools=ToolRegistry([tool]))
    handler = AgentRouterHandler(loop, InMemoryAgentStateStore())
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_agent_handler] = lambda: handler

    with TestClient(app) as client:
        response = client.post("/agent/chat", json={"message": "Show OTHER123 progress"})
        assert response.status_code == 200
        body = response.json()
        assert body["tool_calls"][0]["status"] == "invalid_arguments"
        assert tool_calls == []

        forged_role = client.post("/agent/chat", json={"message": "Hi", "role": "faculty"})
        assert forged_role.status_code == 422
