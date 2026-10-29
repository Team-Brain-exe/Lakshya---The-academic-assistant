from __future__ import annotations

import pytest

from ai.config import AIConfig, AIConfigurationError


def test_config_uses_only_selected_environment_model_ids():
    config = AIConfig.from_env({
        "TOKEN_FACTORY_API_KEY": "example-not-a-real-key",
        "TOKEN_FACTORY_BASE_URL": "https://factory.example/v1",
        "MODEL_TAGGING": "org/nano-model-test",
        "MODEL_GENERATION": "org/super-model-test",
    })

    assert config.model_for("tagging") == "org/nano-model-test"
    assert config.model_for("generation") == "org/super-model-test"
    with pytest.raises(AIConfigurationError, match="MODEL_AGENT"):
        config.model_for("agent")


def test_config_rejects_missing_credentials_without_printing_them():
    config = AIConfig.from_env({"MODEL_TAGGING": "nano-test"})

    with pytest.raises(AIConfigurationError, match="TOKEN_FACTORY_API_KEY"):
        config.create_client()


def test_config_rejects_unknown_model_task():
    config = AIConfig.from_env({})

    with pytest.raises(AIConfigurationError, match="Unknown model task"):
        config.model_for("made-up")


def test_config_does_not_guess_or_default_model_ids():
    config = AIConfig.from_env({
        "TOKEN_FACTORY_API_KEY": "example-not-a-real-key",
        "TOKEN_FACTORY_BASE_URL": "https://factory.example/v1",
    })

    with pytest.raises(AIConfigurationError, match="MODEL_TAGGING"):
        config.model_for("tagging")
