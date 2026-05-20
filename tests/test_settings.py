"""Iris AI Gateway - 配置测试"""

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

    assert any(model["id"] == "gpt-4o" for model in settings.available_models)
    assert settings.model_aliases["claude-sonnet-4"] == "claude-sonnet-4-20250514"


def test_settings_detects_production_environment():
    settings = Settings(_env_file=None, iris_environment="production")

    assert settings.is_production is True
