"""Environment-backed Token Factory configuration with no model-ID defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

from .token_factory import TokenFactoryClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_VARIABLES = {
    "tagging": "MODEL_TAGGING",
    "generation": "MODEL_GENERATION",
    "agent": "MODEL_AGENT",
    "reasoning": "MODEL_REASONING",
}


class AIConfigurationError(RuntimeError):
    """Missing or invalid AI configuration; never contains secret values."""


@dataclass(frozen=True)
class AIConfig:
    api_key: str | None
    base_url: str | None
    model_tagging: str | None = None
    model_generation: str | None = None
    model_agent: str | None = None
    model_reasoning: str | None = None
    timeout_seconds: float = 45.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "AIConfig":
        """Load values from .env/process environment, or a test-supplied mapping."""
        if environ is None:
            load_dotenv(PROJECT_ROOT / ".env")
            source: Mapping[str, str] = os.environ
        else:
            source = environ

        def clean(name: str) -> str | None:
            value = source.get(name)
            return value.strip() if isinstance(value, str) and value.strip() else None

        return cls(
            api_key=clean("TOKEN_FACTORY_API_KEY"),
            base_url=clean("TOKEN_FACTORY_BASE_URL"),
            model_tagging=clean("MODEL_TAGGING"),
            model_generation=clean("MODEL_GENERATION"),
            model_agent=clean("MODEL_AGENT"),
            model_reasoning=clean("MODEL_REASONING"),
        )

    def model_for(self, task: str) -> str:
        env_name = MODEL_VARIABLES.get(task)
        if env_name is None:
            raise AIConfigurationError(f"Unknown model task: {task}")
        model = getattr(self, f"model_{task}")
        if not model:
            raise AIConfigurationError(f"Missing required environment variable: {env_name}")
        return model

    def create_client(self) -> TokenFactoryClient:
        missing = []
        if not self.api_key:
            missing.append("TOKEN_FACTORY_API_KEY")
        if not self.base_url:
            missing.append("TOKEN_FACTORY_BASE_URL")
        if missing:
            raise AIConfigurationError("Missing required environment variables: " + ", ".join(missing))
        try:
            return TokenFactoryClient(
                api_key=self.api_key or "",
                base_url=self.base_url or "",
                timeout=self.timeout_seconds,
            )
        except ValueError as exc:
            # Do not include credentials or URL values in configuration errors.
            raise AIConfigurationError(str(exc)) from exc

    def client_for(self, task: str) -> tuple[TokenFactoryClient, str]:
        model = self.model_for(task)
        return self.create_client(), model
