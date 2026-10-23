"""Optional, environment-backed runtime bootstrap for authenticated agent routes."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from ai.config import AIConfig, AIConfigurationError
from ai.tool_contracts import build_tool_registry
from sqlalchemy import text

from .agent_api import build_postgres_agent_handler_factory, install_agent_handler_factory


def build_agent_tool_registry(connection: Any):
    """Bind only implemented, server-authorized tools to the shared contracts.

    The quiz handler verifies faculty ownership of both the module and CO before
    generation and persists every question as an AI draft. Other contracts stay
    hidden until their production adapters are available.
    """
    from .. import agent_tools

    def generate_quiz_drafts(args: dict[str, Any], current_user: dict[str, Any]) -> dict[str, Any]:
        validated = agent_tools.GenerateQuizArgs.model_validate(args)
        question_ids = agent_tools.generate_quiz(validated, current_user, connection)
        return {
            "drafts": [{
                "question_ids": question_ids,
                "question_count": len(question_ids),
            }]
        }

    return build_tool_registry({"generate_quiz": generate_quiz_drafts})


def _execute_usage_insert(connection: Any, statement: str, parameters: dict[str, Any]) -> None:
    """Isolate optional usage-log failures so they do not poison the request transaction."""
    try:
        with connection.begin_nested():
            connection.execute(text(statement), parameters)
    except Exception:
        # Usage logging is best-effort; the agent/API must not fail on telemetry.
        return


def agent_usage_recorder_factory(connection: Any) -> Callable[[dict[str, Any]], None]:
    """Log model-call metadata without storing prompts, credentials, or raw tool args."""
    def record(entry: dict[str, Any]) -> None:
        safe_args = {
            key: entry[key]
            for key in ("batch_number", "attempt")
            if isinstance(entry.get(key), int) and not isinstance(entry.get(key), bool)
        }
        _execute_usage_insert(
            connection,
            "INSERT INTO agent_logs "
            "(user_id, role, kind, step, model, prompt_tokens, completion_tokens, "
            "total_tokens, latency_ms, args, error) "
            "VALUES (:user_id, :role, 'ai_call', :step, :model, :prompt_tokens, "
            ":completion_tokens, :total_tokens, :latency_ms, CAST(:args AS jsonb), :error)",
            {
                "user_id": entry.get("user_id"),
                "role": entry.get("role"),
                "step": str(entry.get("step") or "agent"),
                "model": str(entry.get("model") or "unknown"),
                "prompt_tokens": entry.get("prompt_tokens"),
                "completion_tokens": entry.get("completion_tokens"),
                "total_tokens": entry.get("total_tokens"),
                "latency_ms": entry.get("latency_ms"),
                "args": json.dumps(safe_args),
                "error": str(entry.get("error"))[:120] if entry.get("error") else None,
            },
        )
    return record


def tool_usage_recorder_factory(connection: Any) -> Callable[[dict[str, Any]], None]:
    """Log tool names/status only; model-supplied arguments may contain private data."""
    def record(entry: dict[str, Any]) -> None:
        _execute_usage_insert(
            connection,
            "INSERT INTO agent_logs "
            "(user_id, role, kind, step, tool_name, latency_ms, args, result_summary, error) "
            "VALUES (:user_id, :role, 'tool_call', 'agent', :tool_name, :latency_ms, "
            "CAST('{}' AS jsonb), :result_summary, :error)",
            {
                "user_id": entry.get("user_id"),
                "role": entry.get("role"),
                "tool_name": str(entry.get("tool_name") or "unknown")[:120],
                "latency_ms": entry.get("latency_ms"),
                "result_summary": str(entry.get("status") or "unknown")[:120],
                "error": str(entry.get("error"))[:120] if entry.get("error") else None,
            },
        )
    return record


def configure_agent_runtime(app: Any, *, config: AIConfig | None = None) -> bool:
    """Install the request-scoped runtime only when required model config exists.

    Without a Token Factory key, HTTPS base URL, agent model, and generation
    model, the app remains importable and the route returns AGENT_NOT_CONFIGURED.
    """
    settings = config or AIConfig.from_env()
    try:
        model = settings.model_for("agent")
        settings.model_for("generation")
        client = settings.create_client()
    except (AIConfigurationError, ValueError):
        return False

    factory = build_postgres_agent_handler_factory(
        client,
        model=model,
        tool_registry_factory=build_agent_tool_registry,
        usage_recorder_factory=agent_usage_recorder_factory,
        tool_usage_recorder_factory=tool_usage_recorder_factory,
    )
    install_agent_handler_factory(app, factory)
    app.state.agent_client = client
    return True


def close_agent_runtime(app: Any) -> None:
    """Close the shared HTTP client during FastAPI shutdown."""
    client = getattr(app.state, "agent_client", None)
    if client is not None:
        client.close()
