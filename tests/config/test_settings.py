"""Iris AI Gateway - 配置测试"""

import pytest
from pydantic import ValidationError

import bootstrap
from config.settings import Settings


def test_settings_parses_api_keys_and_cors_origins():
    settings = Settings(
        _env_file=None,
        iris_api_keys="key-a, key-b",
        cors_origins="http://localhost:3000, https://example.test",
    )

    assert settings.api_key_list == ["key-a", "key-b"]
    assert settings.cors_origin_list == ["http://localhost:3000", "https://example.test"]


def test_settings_exposes_model_configuration_defaults():
    settings = Settings(_env_file=None)

    assert any(model["id"] == "kimi-for-coding" for model in settings.available_models)
    assert settings.model_aliases["coding"] == "kimi-for-coding"
    assert settings.model_providers["kimi-for-coding"] == "anthropic"


def test_settings_detects_production_environment():
    settings = Settings(_env_file=None, iris_environment="Production")

    assert settings.is_production is True


def test_settings_normalizes_string_enum_values():
    settings = Settings(
        _env_file=None,
        memory_backend="SQLITE",
        default_provider="Anthropic",
    )

    assert settings.memory_backend == "sqlite"
    assert settings.default_provider == "anthropic"


def test_settings_rejects_invalid_memory_backend():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, memory_backend="redis")


def test_settings_normalizes_model_provider_names():
    settings = Settings(
        _env_file=None,
        model_providers={"custom-claude": "Anthropic"},
    )

    assert settings.model_providers == {"custom-claude": "anthropic"}


def test_settings_rejects_invalid_model_provider():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            model_providers={"custom": "local"},
        )


def test_bootstrap_rejects_open_cors_in_production(monkeypatch):
    monkeypatch.setattr(
        bootstrap,
        "settings",
        Settings(
            _env_file=None,
            iris_environment="production",
            cors_origins="*",
        ),
    )

    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        bootstrap.check_cors_config()
