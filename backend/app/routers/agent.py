"""Authenticated agent chat and explicit proposal-confirmation endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ..deps import get_current_user
from ..errors import AppError
from ..services.agent_api import AgentRouterHandler

router = APIRouter(tags=["agent"])


class AgentChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None


class AgentConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: UUID
    approve: bool


def request_connection():
    # Lazy import keeps pure handler/unit tests independent of DATABASE_URL.
    from ..db import get_conn
    yield from get_conn()


def get_agent_handler(
    request: Request,
    connection=Depends(request_connection),
) -> AgentRouterHandler:
    factory = getattr(request.app.state, "agent_handler_factory", None)
    if not callable(factory):
        raise AppError(503, "AGENT_NOT_CONFIGURED", "Agent tools are not configured on this server.")
    try:
        return factory(connection)
    except Exception as exc:
        raise AppError(503, "AGENT_NOT_CONFIGURED", "Agent tools are not configured on this server.") from exc


def _json_response(status_code: int, body: dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=body)


@router.post("/agent/chat")
def chat(
    payload: AgentChatRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    handler: AgentRouterHandler = Depends(get_agent_handler),
):
    """The user's identity and role come only from the bearer-token dependency."""
    status_code, body = handler.chat(
        current_user,
        payload.message,
        conversation_id=str(payload.conversation_id) if payload.conversation_id else None,
    )
    return _json_response(status_code, body)


@router.post("/agent/confirm")
def confirm(
    payload: AgentConfirmRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    handler: AgentRouterHandler = Depends(get_agent_handler),
):
    """Approve or cancel a user-owned pending proposal; writes occur only here."""
    status_code, body = handler.confirm(
        current_user,
        str(payload.proposal_id),
        approve=payload.approve,
    )
    return _json_response(status_code, body)
