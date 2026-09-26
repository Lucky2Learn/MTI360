"""Toolchain smoke tests for settings loading (T00-02, updated for T00-04).

Environment isolation is provided by the autouse fixture in ``conftest.py``.
Per-environment rules are tested in ``test_settings_environments.py``.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_defaults_are_secure() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.app_debug is False
    assert settings.log_level == "INFO"


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DEBUG", "true")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    settings = Settings(_env_file=None)

    assert settings.app_debug is True
    assert settings.log_level == "WARNING"


def test_unknown_app_env_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
