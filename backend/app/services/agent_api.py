"""Framework-independent handler for the /agent API contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from ai.agent import (
    AgentError,
    AgentLoop,
    AgentPermissionError,
    ProposalConflictError,
    ProposalExecutionError,
    ProposalNotFoundError,
    ToolRegistry,
)
from .agent_state import ConversationStore, PostgresAgentStateStore


def format_error(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": {}}}


class AgentRouterHandler:
    """Run the loop using the authenticated identity and owner-scoped history."""

    def __init__(self, loop: AgentLoop, state_store: ConversationStore) -> None:
        self.loop = loop
        self.state_store = state_store

    def chat(
        self,
        current_user: dict[str, Any],
        message: str,
        conversation_id: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        user_id = current_user.get("user_id")
        role = current_user.get("role")
        if not isinstance(user_id, str) or role not in {"student", "faculty"}:
            return 403, format_error("FORBIDDEN", "A valid authenticated user is required.")
        if not isinstance(message, str) or not message.strip():
            return 400, format_error("BAD_REQUEST", "message must not be empty.")

        try:
            if conversation_id is not None:
                try:
                    selected_id = str(UUID(conversation_id))
                except (TypeError, ValueError, AttributeError):
                    return 400, format_error("BAD_REQUEST", "conversation_id must be a UUID.")
                history = self.state_store.load_conversation(selected_id, user_id, role)
                if history is None:
                    return 404, format_error("NOT_FOUND", "Conversation not found.")
            else:
                selected_id = self.state_store.create_conversation(user_id, role)
                history = []
        except Exception:
            return 503, format_error("AGENT_NOT_CONFIGURED", "The agent state store is not configured.")

        try:
            result = self.loop.run(current_user, message, history=history)
            saved_history = result.history[-40:]
            self.state_store.save_conversation(selected_id, user_id, role, saved_history)
        except AgentPermissionError as exc:
            return 403, format_error(exc.code, str(exc))
        except ValueError as exc:
            return 400, format_error("BAD_REQUEST", str(exc))
        except Exception:
            return 503, format_error("AGENT_NOT_CONFIGURED", "The agent could not process this request.")

        return 200, {
            "conversation_id": selected_id,
            "reply": result.reply,
            "tool_calls": result.tool_calls,
            "proposals": result.proposals,
            "drafts": result.drafts,
        }

    def confirm(
        self,
        current_user: dict[str, Any],
        proposal_id: str,
        approve: bool,
    ) -> tuple[int, dict[str, Any]]:
        if current_user.get("role") not in {"student", "faculty"} or not current_user.get("user_id"):
            return 403, format_error("FORBIDDEN", "A valid authenticated user is required.")
        if not isinstance(proposal_id, str) or not proposal_id:
            return 400, format_error("BAD_REQUEST", "proposal_id is required.")
        try:
            proposal_id = str(UUID(proposal_id))
        except ValueError:
            return 400, format_error("BAD_REQUEST", "proposal_id must be a UUID.")
        if not isinstance(approve, bool):
            return 400, format_error("BAD_REQUEST", "approve must be a boolean.")
        try:
            return 200, self.loop.confirm(current_user, proposal_id, approve=approve)
        except ProposalNotFoundError as exc:
            return 404, format_error(exc.code, str(exc))
        except ProposalConflictError as exc:
            return 409, format_error(exc.code, str(exc))
        except ProposalExecutionError as exc:
            return 500, format_error(exc.code, str(exc))
        except AgentPermissionError as exc:
            return 403, format_error(exc.code, str(exc))
        except AgentError as exc:
            return 503, format_error(exc.code, str(exc))
        except Exception:
            return 503, format_error("AGENT_NOT_CONFIGURED", "The agent proposal store is not configured.")


def build_postgres_agent_handler_factory(
    client: Any,
    *,
    model: str,
    tool_registry_factory: Callable[[Any], ToolRegistry],
    proposal_executors_factory: Callable[[Any], Mapping[str, Callable[[dict[str, Any], dict[str, Any]], Any]]] | None = None,
    usage_recorder_factory: Callable[[Any], Callable[[dict[str, Any]], None] | None] | None = None,
    tool_usage_recorder_factory: Callable[[Any], Callable[[dict[str, Any]], None] | None] | None = None,
    max_steps: int = 6,
) -> Callable[[Any], AgentRouterHandler]:
    """Create a request-scoped handler with PostgreSQL conversation/proposal state.

    Collaborator-owned service adapters are supplied through ``tool_registry_factory``;
    unimplemented tools are omitted from the registry and never advertised to a model.
    """
    def create(connection: Any) -> AgentRouterHandler:
        state_store = PostgresAgentStateStore(connection)
        registry = tool_registry_factory(connection)
        executors = proposal_executors_factory(connection) if proposal_executors_factory else {}
        usage_recorder = usage_recorder_factory(connection) if usage_recorder_factory else None
        tool_usage_recorder = tool_usage_recorder_factory(connection) if tool_usage_recorder_factory else None
        loop = AgentLoop(
            client,
            model=model,
            tools=registry,
            proposal_store=state_store,
            proposal_executors=executors,
            max_steps=max_steps,
            usage_recorder=usage_recorder,
            tool_usage_recorder=tool_usage_recorder,
        )
        return AgentRouterHandler(loop, state_store)
    return create


def install_agent_handler_factory(app: Any, factory: Callable[[Any], AgentRouterHandler]) -> None:
    """Install the collaborator-wired agent runtime on the FastAPI app."""
    app.state.agent_handler_factory = factory
