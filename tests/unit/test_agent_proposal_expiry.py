"""Proposal expiry and stuck-confirm handling, driven by a scripted connection (no database)."""
import pytest

from ai.agent import ProposalConflictError, ProposalNotFoundError
from app.services.agent_state import PostgresAgentStateStore

USER = "11111111-1111-1111-1111-111111111111"
OTHER = "22222222-2222-2222-2222-222222222222"


class Result:
    def __init__(self, row=None, rowcount=0):
        self._row = row
        self.rowcount = rowcount

    def mappings(self):
        return self

    def fetchone(self):
        return self._row


class ScriptedConnection:
    """Returns the scripted results in order and records every statement it was given."""

    def __init__(self, *results):
        self.results = list(results)
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((str(statement), params))
        return self.results.pop(0)


def processing_row():
    return {"id": "p1", "user_id": USER, "role": "faculty", "tool_name": "propose_schedule_event",
            "arguments": {"subject_id": "s1"}, "status": "processing", "created_at": "2026-10-27T00:00:00Z"}


def existing(status="pending", expired=False, user=USER):
    return {"user_id": user, "role": "faculty", "status": status, "expired": expired}


def test_a_stuck_confirm_is_failed_before_any_claim_and_is_never_retried():
    conn = ScriptedConnection(Result(rowcount=1), Result(row=None), Result(row=existing(status="failed")))
    with pytest.raises(ProposalConflictError, match="no longer pending"):
        PostgresAgentStateStore(conn).claim("p1", USER, "faculty")
    assert "status = 'failed'" in conn.statements[0][0]
    assert "status = 'pending'" in conn.statements[1][0]


def test_an_expired_pending_proposal_cannot_be_claimed():
    conn = ScriptedConnection(Result(rowcount=0), Result(row=None), Result(row=existing(expired=True)))
    with pytest.raises(ProposalConflictError, match="expired"):
        PostgresAgentStateStore(conn).claim("p1", USER, "faculty")


def test_a_fresh_pending_proposal_is_claimed_and_timestamped():
    conn = ScriptedConnection(Result(rowcount=0), Result(row=processing_row()))
    claimed = PostgresAgentStateStore(conn).claim("p1", USER, "faculty")
    assert claimed.status == "processing"
    assert "claimed_at = now()" in conn.statements[1][0]


def test_another_user_gets_not_found_rather_than_a_hint():
    conn = ScriptedConnection(Result(rowcount=0), Result(row=None), Result(row=existing(user=OTHER)))
    with pytest.raises(ProposalNotFoundError):
        PostgresAgentStateStore(conn).claim("p1", USER, "faculty")
