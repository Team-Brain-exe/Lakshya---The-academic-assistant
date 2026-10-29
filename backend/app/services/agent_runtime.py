"""Optional, environment-backed runtime bootstrap for authenticated agent routes."""
from __future__ import annotations

import json
from collections.abc import Callable
from functools import partial
from typing import Any

from ai.config import AIConfig, AIConfigurationError
from ai.tool_contracts import build_tool_registry
from sqlalchemy import text

from .agent_api import build_postgres_agent_handler_factory, install_agent_handler_factory
from .agent_dev_stores import build_dev_analytics_store, validate_dev_store_config
from .agent_errors import report_app_errors


def build_agent_tool_registry(
    connection: Any,
    analytics_store_factory: Callable[[Any], Any] | None = None,
):
    """Bind only implemented, server-authorized tools to the shared contracts.

    The quiz handler verifies faculty ownership of both the module and CO before
    generation and persists every question as an AI draft.

    The analytics tools take an AnalyticsStore, not a database connection. They are
    bound only when ``analytics_store_factory(connection)`` returns a store. Without
    one, they stay hidden from the model.
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

    handlers: dict[str, Callable[[dict[str, Any], dict[str, Any]], Any]] = {
        "generate_quiz": generate_quiz_drafts,
    }

    if analytics_store_factory is not None:
        store = analytics_store_factory(connection)
        if store is not None:
            _bind_analytics_tools(handlers, agent_tools, store)

    # Surface backend AppError messages to the model as tool results.
    handlers = {name: report_app_errors(fn) for name, fn in handlers.items()}
    return build_tool_registry(handlers)


def _bind_analytics_tools(handlers: dict[str, Any], agent_tools: Any, store: Any) -> None:
    """Pass the server-held store as the third argument. The model never chooses it."""

    def bind(tool_fn, args_model, shape):
        def handler(args: dict[str, Any], current_user: dict[str, Any]) -> Any:
            validated = args_model.model_validate(args)
            return shape(tool_fn(validated, current_user, store))
        return handler

    handlers["find_weak_COs"] = bind(
        agent_tools.find_weak_COs, agent_tools.FindWeakCOsArgs,
        lambda rows: {"weak_cos": rows},
    )
    handlers["get_co_attainment"] = bind(
        agent_tools.get_co_attainment, agent_tools.GetCOAttainmentArgs,
        lambda rows: {"cos": rows},
    )
    handlers["get_student_progress"] = bind(
        agent_tools.get_student_progress, agent_tools.GetStudentProgressArgs,
        lambda result: result,
    )


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
    validate_dev_store_config()  # fails at startup if dev-only data is enabled in production
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
        tool_registry_factory=partial(
            build_agent_tool_registry,
            analytics_store_factory=build_dev_analytics_store,
        ),
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
