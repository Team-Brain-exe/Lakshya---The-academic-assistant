"""Conversation and confirmation-proposal storage for the role-scoped agent."""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy import text

from ai.agent import (
    AgentProposal,
    InMemoryProposalStore,
    ProposalConflictError,
    ProposalNotFoundError,
)


class ConversationStore(Protocol):
    def create_conversation(self, user_id: str, role: str) -> str: ...
    def load_conversation(self, conversation_id: str, user_id: str, role: str) -> list[dict[str, Any]] | None: ...
    def save_conversation(self, conversation_id: str, user_id: str, role: str, messages: Sequence[Mapping[str, Any]]) -> None: ...


class InMemoryAgentStateStore(InMemoryProposalStore):
    """In-memory conversation/proposal store for unit tests and local demos only."""

    def __init__(self) -> None:
        super().__init__()
        self._conversations: dict[str, dict[str, Any]] = {}
        self._conversation_lock = threading.RLock()

    def create_conversation(self, user_id: str, role: str) -> str:
        conversation_id = str(uuid.uuid4())
        with self._conversation_lock:
            self._conversations[conversation_id] = {
                "user_id": user_id,
                "role": role,
                "messages": [],
            }
        return conversation_id

    def load_conversation(self, conversation_id: str, user_id: str, role: str) -> list[dict[str, Any]] | None:
        with self._conversation_lock:
            record = self._conversations.get(conversation_id)
            if record is None or record["user_id"] != user_id or record["role"] != role:
                return None
            return [dict(message) for message in record["messages"]]

    def save_conversation(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        messages: Sequence[Mapping[str, Any]],
    ) -> None:
        with self._conversation_lock:
            record = self._conversations.get(conversation_id)
            if record is None or record["user_id"] != user_id or record["role"] != role:
                raise KeyError("Conversation not found")
            record["messages"] = [dict(message) for message in messages]


class PostgresAgentStateStore:
    """PostgreSQL adapter. Pass the request-scoped SQLAlchemy connection."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def create_conversation(self, user_id: str, role: str) -> str:
        conversation_id = str(uuid.uuid4())
        self.connection.execute(
            text(
                "INSERT INTO agent_conversations (id, user_id, role, messages) "
                "VALUES (:id, :user_id, :role, CAST(:messages AS jsonb))"
            ),
            {"id": conversation_id, "user_id": user_id, "role": role, "messages": "[]"},
        )
        return conversation_id

    def load_conversation(self, conversation_id: str, user_id: str, role: str) -> list[dict[str, Any]] | None:
        row = self.connection.execute(
            text(
                "SELECT messages FROM agent_conversations "
                "WHERE id = :id AND user_id = :user_id AND role = :role"
            ),
            {"id": conversation_id, "user_id": user_id, "role": role},
        ).mappings().fetchone()
        if row is None:
            return None
        messages = row["messages"]
        if isinstance(messages, str):
            messages = json.loads(messages)
        if not isinstance(messages, list):
            return []
        return [dict(message) for message in messages if isinstance(message, Mapping)]

    def save_conversation(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        messages: Sequence[Mapping[str, Any]],
    ) -> None:
        encoded = json.dumps([dict(message) for message in messages], ensure_ascii=False)
        result = self.connection.execute(
            text(
                "UPDATE agent_conversations SET messages = CAST(:messages AS jsonb), updated_at = now() "
                "WHERE id = :id AND user_id = :user_id AND role = :role"
            ),
            {"id": conversation_id, "user_id": user_id, "role": role, "messages": encoded},
        )
        if result.rowcount != 1:
            raise KeyError("Conversation not found")

    def create(self, user_id: str, role: str, tool_name: str, arguments: dict[str, Any]) -> AgentProposal:
        proposal_id = str(uuid.uuid4())
        encoded_args = json.dumps(arguments, ensure_ascii=False)
        row = self.connection.execute(
            text(
                "INSERT INTO agent_proposals (id, user_id, role, tool_name, arguments, status) "
                "VALUES (:id, :user_id, :role, :tool_name, CAST(:arguments AS jsonb), 'pending') "
                "RETURNING created_at"
            ),
            {
                "id": proposal_id,
                "user_id": user_id,
                "role": role,
                "tool_name": tool_name,
                "arguments": encoded_args,
            },
        ).mappings().fetchone()
        return AgentProposal(
            proposal_id=proposal_id,
            user_id=user_id,
            role=role,
            tool_name=tool_name,
            arguments=dict(arguments),
            status="pending",
            created_at=row["created_at"] if row else datetime.now(timezone.utc),
        )

    def get(self, proposal_id: str) -> AgentProposal | None:
        row = self.connection.execute(
            text(
                "SELECT id, user_id, role, tool_name, arguments, status, created_at "
                "FROM agent_proposals WHERE id = :id"
            ),
            {"id": proposal_id},
        ).mappings().fetchone()
        return self._proposal(row) if row else None

    def get_owned(self, proposal_id: str, user_id: str, role: str) -> AgentProposal | None:
        row = self.connection.execute(
            text(
                "SELECT id, user_id, role, tool_name, arguments, status, created_at "
                "FROM agent_proposals WHERE id = :id AND user_id = :user_id AND role = :role"
            ),
            {"id": proposal_id, "user_id": user_id, "role": role},
        ).mappings().fetchone()
        return self._proposal(row) if row else None

    def claim(self, proposal_id: str, user_id: str, role: str) -> AgentProposal:
        ttl_minutes = 15  # a pending proposal older than this can no longer be confirmed
        timeout_minutes = 5  # a confirm stuck in 'processing' longer than this is failed
        owner = {"id": proposal_id, "user_id": user_id, "role": role}
        # A confirm that started and never finished is failed, never retried: its calendar
        # write may already have happened.
        self.connection.execute(
            text(
                "UPDATE agent_proposals SET status = 'failed', resolved_at = now() "
                "WHERE id = :id AND user_id = :user_id AND role = :role AND status = 'processing' "
                "AND claimed_at < now() - make_interval(mins => :timeout)"
            ),
            {**owner, "timeout": timeout_minutes},
        )
        row = self.connection.execute(
            text(
                "UPDATE agent_proposals SET status = 'processing', claimed_at = now() "
                "WHERE id = :id AND user_id = :user_id AND role = :role AND status = 'pending' "
                "AND created_at > now() - make_interval(mins => :ttl) "
                "RETURNING id, user_id, role, tool_name, arguments, status, created_at"
            ),
            {**owner, "ttl": ttl_minutes},
        ).mappings().fetchone()
        if row is not None:
            return self._proposal(row)
        existing = self.connection.execute(
            text(
                "SELECT user_id, role, status, "
                "created_at < now() - make_interval(mins => :ttl) AS expired "
                "FROM agent_proposals WHERE id = :id"
            ),
            {"id": proposal_id, "ttl": ttl_minutes},
        ).mappings().fetchone()
        if existing is None or str(existing["user_id"]) != user_id or existing["role"] != role:
            raise ProposalNotFoundError("Proposal not found")
        if existing["status"] == "pending" and existing["expired"]:
            raise ProposalConflictError("This proposal has expired. Ask for a new one.")
        raise ProposalConflictError("Proposal is no longer pending")

    def finish(self, proposal_id: str, status: str) -> None:
        if status not in {"approved", "cancelled", "failed"}:
            raise ValueError("Invalid final proposal status")
        result = self.connection.execute(
            text(
                "UPDATE agent_proposals SET status = :status, resolved_at = now() "
                "WHERE id = :id AND status = 'processing'"
            ),
            {"id": proposal_id, "status": status},
        )
        if result.rowcount != 1:
            raise ProposalConflictError("Proposal is not being processed")

    @staticmethod
    def _proposal(row: Mapping[str, Any]) -> AgentProposal:
        arguments = row["arguments"]
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        return AgentProposal(
            proposal_id=str(row["id"]),
            user_id=str(row["user_id"]),
            role=row["role"],
            tool_name=row["tool_name"],
            arguments=dict(arguments) if isinstance(arguments, Mapping) else {},
            status=row["status"],
            created_at=row["created_at"],
        )
