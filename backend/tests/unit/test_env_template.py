"""``backend/.env.example`` and ``Settings`` stay consistent (T00-04).

Every template variable is a ``Settings`` field and every field is documented
in the template. The template itself must be a valid development configuration
and must be rejected as a production configuration (it holds placeholders only).
"""

from pathlib import Path

import pytest

from app.core.config import ConfigurationError, Settings, load_settings

TEMPLATE = Path(__file__).resolve().parents[2] / ".env.example"


def template_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in TEMPLATE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            name, _, value = line.partition("=")
            values[name.strip()] = value.strip()
    return values


def test_template_declares_exactly_the_settings_fields() -> None:
    declared = set(template_values())
    fields = {name.upper() for name in Settings.model_fields}

    assert declared - fields == set(), "template variables without a Settings field"
    assert fields - declared == set(), "Settings fields missing from the template"


def test_template_is_a_valid_development_configuration() -> None:
    settings = load_settings(_env_file=TEMPLATE)

    assert settings.app_env == "development"
    assert settings.app_debug is True  # the template enables debug for local work


def test_template_values_are_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in template_values().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(ConfigurationError) as caught:
        load_settings(_env_file=None)

    message = str(caught.value)
    for name in ("APP_DEBUG", "SESSION_SECRET", "AI_PROVIDER", "DATABASE_URL"):
        assert f"{name}:" in message
