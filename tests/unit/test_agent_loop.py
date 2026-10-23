from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from ai.agent import (
    AgentLoop,
    AgentTool,
    InMemoryProposalStore,
    ProposalConflictError,
    ToolRegistry,
)


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, *, model, messages, tools=None, tool_choice=None, **kwargs):
        self.calls.append({
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
            **kwargs,
        })
        return self.responses.pop(0)


def response(content=None, tool_calls=None, usage=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls or [], usage=usage or {})


def call(tool_name, arguments, call_id="call-1"):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": tool_name, "arguments": json.dumps(arguments)},
    }


def read_tool(name="lookup", roles=("student", "faculty"), handler=None, parameters=None, **kwargs):
    return AgentTool(
        name=name,
        description=f"Read {name} data",
        parameters=parameters or {
            "type": "object",
            "properties": {"topic": {"type": "string", "minLength": 1}},
            "required": ["topic"],
            "additionalProperties": False,
        },
        roles=frozenset(roles),
        handler=handler or (lambda args, user: {"topic": args["topic"], "value": 42}),
        **kwargs,
    )


def test_role_without_registered_tools_gets_safe_unavailable_reply_without_model_call():
    client = FakeClient([])
    loop = AgentLoop(client, model="agent-test", tools=ToolRegistry())

    result = loop.run({"user_id": "student-1", "role": "student"}, "Show my progress")

    assert client.calls == []
    assert result.tool_calls == []
    assert "not configured" in result.reply.lower()
    assert result.history[-1] == {"role": "assistant", "content": result.reply}


def test_tool_result_is_returned_to_model_before_final_reply():
    tool = read_tool()
    client = FakeClient([
        response(tool_calls=[call("lookup", {"topic": "CO1"})], usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}),
        response(content="CO1 attainment is 80%.", usage={"prompt_tokens": 9, "completion_tokens": 5, "total_tokens": 14}),
    ])
    usage = []
    registry = ToolRegistry([tool])
    loop = AgentLoop(client, model="agent-test", tools=registry, usage_recorder=usage.append)

    result = loop.run({"user_id": "u1", "role": "faculty"}, "Find CO1 attainment")

    assert result.reply == "CO1 attainment is 80%."
    assert result.tool_calls == [{"name": "lookup", "status": "ok"}]
    assert len(client.calls) == 2
    second_messages = client.calls[1]["messages"]
    assert second_messages[-2]["role"] == "tool"
    assert json.loads(second_messages[-2]["content"]) == {"topic": "CO1", "value": 42}
    assert len(usage) == 2


def test_student_never_receives_faculty_tool_schema():
    registry = ToolRegistry([
        read_tool(name="faculty_report", roles=("faculty",)),
        read_tool(name="my_progress", roles=("student",)),
    ])
    client = FakeClient([response(content="Your progress is in the tool results.")])
    loop = AgentLoop(client, model="agent-test", tools=registry)

    loop.run({"user_id": "student-1", "role": "student", "student_id": "s1"}, "Show my progress")

    exposed_names = [item["function"]["name"] for item in client.calls[0]["tools"]]
    assert exposed_names == ["my_progress"]


def test_student_cannot_pass_another_students_usn_to_tool():
    calls = []
    student_progress = read_tool(
        name="get_my_progress",
        roles=("student",),
        parameters={
            "type": "object",
            "properties": {"subject_id": {"type": "string", "minLength": 1}},
            "required": ["subject_id"],
            "additionalProperties": False,
        },
        handler=lambda args, user: calls.append((args, user)) or {"co_scores": []},
    )
    client = FakeClient([
        response(tool_calls=[call("get_my_progress", {"subject_id": "sub1", "usn": "OTHER123"})]),
        response(content="I can only access your own progress.")
    ])
    loop = AgentLoop(client, model="agent-test", tools=ToolRegistry([student_progress]))

    result = loop.run({"user_id": "u1", "role": "student", "student_id": "s1", "usn": "OWN123"}, "Show OTHER123 progress")

    assert calls == []
    assert result.tool_calls[0]["status"] == "invalid_arguments"
    assert result.reply == "I can only access your own progress."


def test_tool_loop_is_capped_at_configured_model_steps():
    tool = read_tool()
    client = FakeClient([
        response(tool_calls=[call("lookup", {"topic": "again"}, "call-1")]),
        response(tool_calls=[call("lookup", {"topic": "again"}, "call-2")]),
        response(content="This should not be requested"),
    ])
    loop = AgentLoop(client, model="agent-test", tools=ToolRegistry([tool]), max_steps=2)

    result = loop.run({"user_id": "u1", "role": "faculty"}, "Keep looking")

    assert len(client.calls) == 2
    assert result.loop_limited is True
    assert "limit" in result.reply.lower()


def test_schedule_action_is_only_a_proposal_until_user_confirms():
    store = InMemoryProposalStore()
    executions = []
    schedule_tool = AgentTool(
        name="propose_schedule_event",
        description="Propose a calendar event; it is not saved until confirmed.",
        parameters={
            "type": "object",
            "properties": {"title": {"type": "string", "minLength": 1}},
            "required": ["title"],
            "additionalProperties": False,
        },
        roles=frozenset({"faculty"}),
        handler=None,
        mutates=True,
        confirmation_required=True,
    )
    client = FakeClient([
        response(tool_calls=[call("propose_schedule_event", {"title": "Quiz review"})]),
        response(content="I proposed the event. It will be saved only after you approve it."),
    ])
    loop = AgentLoop(
        client,
        model="agent-test",
        tools=ToolRegistry([schedule_tool]),
        proposal_store=store,
        proposal_executors={"propose_schedule_event": lambda args, user: executions.append((args, user)) or {"event_id": "event-1"}},
    )
    user = {"user_id": "faculty-1", "role": "faculty"}

    result = loop.run(user, "Schedule a quiz review")

    assert executions == []
    assert result.proposals[0]["status"] == "pending_confirmation"
    proposal_id = result.proposals[0]["proposal_id"]
    confirmation = loop.confirm(user, proposal_id, approve=True)
    assert confirmation["status"] == "approved"
    assert executions == [({"title": "Quiz review"}, user)]
    with pytest.raises(ProposalConflictError):
        loop.confirm(user, proposal_id, approve=True)


def test_proposals_cannot_be_looked_up_by_a_different_user():
    store = InMemoryProposalStore()
    proposal = store.create("faculty-1", "faculty", "propose_schedule_event", {"title": "Review"})

    assert store.get_owned(proposal.proposal_id, "faculty-2", "faculty") is None
    assert store.get_owned(proposal.proposal_id, "faculty-1", "faculty").proposal_id == proposal.proposal_id


def test_unreviewed_mutating_tool_cannot_be_registered():
    with pytest.raises(ValueError, match="confirmation or review"):
        AgentTool(
            name="unsafe_write",
            description="Unsafe write",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            roles=frozenset({"faculty"}),
            handler=lambda args, user: {"saved": True},
            mutates=True,
        )


def test_system_prompt_requires_grounding_and_unknown_when_retrieval_is_empty():
    tool = read_tool()
    loop = AgentLoop(FakeClient([response(content="I don't know.")]), model="agent-test", tools=ToolRegistry([tool]))

    loop.run({"user_id": "u1", "role": "student"}, "Question")

    prompt = loop._system_prompt("student")
    assert "tool result" in prompt.lower()
    assert "do not know" in prompt.lower()


def test_single_response_tool_call_burst_is_rejected_before_any_handler_runs():
    executed = []
    tool = read_tool(handler=lambda args, user: executed.append(args) or {"ok": True})
    client = FakeClient([response(tool_calls=[
        call("lookup", {"topic": "one"}, "call-1"),
        call("lookup", {"topic": "two"}, "call-2"),
        call("lookup", {"topic": "three"}, "call-3"),
    ])])
    loop = AgentLoop(
        client,
        model="agent-test",
        tools=ToolRegistry([tool]),
        max_tool_calls_per_response=2,
    )

    result = loop.run({"user_id": "u1", "role": "student"}, "Run many tools")

    assert executed == []
    assert len(client.calls) == 1
    assert result.loop_limited is True
    assert result.tool_calls == [{"name": "batch", "status": "call_limit_exceeded"}]
    assert "too many tool calls" in result.reply.lower()


def test_request_tool_call_budget_rejects_the_next_batch():
    executed = []
    tool = read_tool(handler=lambda args, user: executed.append(args) or {"ok": True})
    client = FakeClient([
        response(tool_calls=[call("lookup", {"topic": "first"}, "call-1")]),
        response(tool_calls=[
            call("lookup", {"topic": "second"}, "call-2"),
            call("lookup", {"topic": "third"}, "call-3"),
        ]),
    ])
    loop = AgentLoop(
        client,
        model="agent-test",
        tools=ToolRegistry([tool]),
        max_tool_calls=2,
        max_tool_calls_per_response=2,
    )

    result = loop.run({"user_id": "u1", "role": "student"}, "Keep using tools")

    assert executed == [{"topic": "first"}]
    assert len(client.calls) == 2
    assert result.loop_limited is True
    assert result.tool_calls[-1] == {"name": "batch", "status": "call_limit_exceeded"}
    assert "tool-call limit" in result.reply.lower()
