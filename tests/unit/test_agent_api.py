from types import SimpleNamespace

from ai.agent import AgentLoop, AgentTool, ToolRegistry
from backend.app.services.agent_api import AgentRouterHandler
from backend.app.services.agent_state import InMemoryAgentStateStore


class FakeClient:
    def __init__(self):
        self.responses = [
            SimpleNamespace(content="First reply", tool_calls=[], usage={}),
            SimpleNamespace(content="Second reply", tool_calls=[], usage={}),
        ]
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def test_agent_api_persists_history_and_scopes_conversations_to_owner():
    client = FakeClient()
    state = InMemoryAgentStateStore()
    student_tool = AgentTool(
        name="student_lookup",
        description="A configured student lookup tool.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        roles=frozenset({"student"}),
        handler=lambda args, user: {},
    )
    loop = AgentLoop(client, model="agent-test", tools=ToolRegistry([student_tool]))
    handler = AgentRouterHandler(loop, state)
    student = {"user_id": "student-1", "role": "student", "student_id": "s1"}

    status, first = handler.chat(student, "Hello")
    assert status == 200
    assert first["reply"] == "First reply"
    conversation_id = first["conversation_id"]

    status, second = handler.chat(student, "Continue", conversation_id)
    assert status == 200
    assert second["reply"] == "Second reply"
    second_messages = client.calls[1]["messages"]
    assert {"role": "user", "content": "Hello"} in second_messages
    assert {"role": "assistant", "content": "First reply"} in second_messages

    status, error = handler.chat({"user_id": "student-2", "role": "student", "student_id": "s2"}, "Read this", conversation_id)
    assert status == 404
    assert error["error"]["code"] == "NOT_FOUND"


def test_agent_api_uses_authenticated_user_and_validates_chat_body():
    loop = AgentLoop(FakeClient(), model="agent-test", tools=ToolRegistry())
    handler = AgentRouterHandler(loop, InMemoryAgentStateStore())

    status, error = handler.chat({"user_id": "u1", "role": "student"}, " ")
    assert status == 400
    assert error["error"]["code"] == "BAD_REQUEST"

    status, error = handler.chat({"user_id": "u1", "role": "admin"}, "hello")
    assert status == 403
    assert error["error"]["code"] == "FORBIDDEN"

    status, error = handler.chat({"user_id": "u1", "role": "student"}, "hello", "not-a-uuid")
    assert status == 400
    assert error["error"]["code"] == "BAD_REQUEST"


def test_agent_api_maps_unavailable_state_storage_to_503():
    class BrokenStateStore:
        def create_conversation(self, user_id, role):
            raise RuntimeError("agent tables are not installed")

    handler = AgentRouterHandler(
        AgentLoop(FakeClient(), model="agent-test", tools=ToolRegistry()),
        BrokenStateStore(),
    )

    status, error = handler.chat({"user_id": "u1", "role": "faculty"}, "hello")

    assert status == 503
    assert error["error"]["code"] == "AGENT_NOT_CONFIGURED"


def test_agent_confirmation_maps_unavailable_proposal_storage_to_503():
    class BrokenProposalStore:
        def get_owned(self, proposal_id, user_id, role):
            raise RuntimeError("agent tables are not installed")

    handler = AgentRouterHandler(
        AgentLoop(FakeClient(), model="agent-test", tools=ToolRegistry(), proposal_store=BrokenProposalStore()),
        InMemoryAgentStateStore(),
    )

    status, error = handler.confirm(
        {"user_id": "faculty-1", "role": "faculty"},
        "f742ca38-149a-4a66-a8f8-d9f16b93b10e",
        approve=True,
    )

    assert status == 503
    assert error["error"]["code"] == "AGENT_NOT_CONFIGURED"
