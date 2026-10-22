"""Small OpenAI-compatible client for Nebius Token Factory.

Keep the base URL configurable: use the exact URL shown in the Token Factory
project settings rather than baking an endpoint into application code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class ChatResult:
    content: str | None
    tool_calls: list[dict[str, Any]]
    usage: dict[str, int]
    raw: Mapping[str, Any]


class TokenFactoryError(RuntimeError):
    """Raised when Token Factory returns an invalid or unsuccessful response."""


class TokenFactoryClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: float = 45.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Token Factory API key must not be empty")
        normalized_base_url = base_url.strip()
        parsed_url = urlsplit(normalized_base_url)
        if (
            parsed_url.scheme.lower() != "https"
            or not parsed_url.netloc
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError("Token Factory base URL must be a valid HTTPS URL")
        self._api_key = api_key
        self._url = f"{normalized_base_url.rstrip('/')}/chat/completions"
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def chat(
        self,
        *,
        model: str,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        if not model.strip():
            raise ValueError("model must not be empty")

        body: dict[str, Any] = {"model": model, "messages": list(messages)}
        if tools is not None:
            body["tools"] = list(tools)
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        response = self._client.post(
            self._url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json=body,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise TokenFactoryError(
                f"Token Factory returned HTTP {exc.response.status_code}"
            ) from exc

        try:
            payload = response.json()
            choice = payload["choices"][0]
            message = choice["message"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise TokenFactoryError("Token Factory response has an unexpected shape") from exc
        if not isinstance(message, Mapping):
            raise TokenFactoryError("Token Factory response has an unexpected shape")

        raw_calls = message.get("tool_calls") or []
        if not isinstance(raw_calls, list):
            raise TokenFactoryError("Token Factory tool_calls must be a list")
        usage = payload.get("usage") or {}
        if not isinstance(usage, Mapping):
            usage = {}
        usage_counts = {
            name: int(usage[name])
            for name in ("prompt_tokens", "completion_tokens", "total_tokens")
            if isinstance(usage.get(name), int) and not isinstance(usage.get(name), bool)
        }
        return ChatResult(
            content=message.get("content"),
            tool_calls=raw_calls,
            usage=usage_counts,
            raw=payload,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TokenFactoryClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
