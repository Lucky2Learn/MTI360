"""Per-environment settings rules, secret masking and ``.env`` isolation (T00-04).

Every rule in docs/architecture/environments.md has a failing and a passing case.
"""

import logging
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import (
    MIN_SECRET_LENGTH,
    ConfigurationError,
    Settings,
    load_settings,
)

# Fixed, fake test values (>= 32 characters, distinct).
TEST_SESSION_SECRET = "mti360-test-session-secret-0123456789abcdef"
TEST_CSRF_SECRET = "mti360-test-csrf-secret-0123456789abcdef"

DEPLOYED = ("staging", "production")
NON_DEVELOPMENT = ("test", "staging", "production")


def _db_url(user: str, password: str = "db-password-9f2c", query: str = "ssl=require") -> SecretStr:
    return SecretStr(f"postgresql+asyncpg://{user}:{password}@db.internal:5432/mti360?{query}")


def deployed_values() -> dict[str, Any]:
    """A complete, valid staging/production configuration built from fake values."""
    return {
        "app_debug": False,
        "log_level": "INFO",
        "database_url": _db_url("mti_app"),
        "migrations_database_url": _db_url("mti_owner"),
        "readonly_database_url": _db_url("mti_readonly"),
        "redis_url": SecretStr("rediss://cache.internal:6380/0"),
        "s3_endpoint_url": "",
        "s3_region": "ap-south-1",
        "s3_bucket": "mti360-deployed",
        "s3_access_key_id": SecretStr("fake-access-key-id-7d1e"),
        "s3_secret_access_key": SecretStr("fake-secret-access-key-7d1e"),
        "session_secret": SecretStr(TEST_SESSION_SECRET),
        "csrf_secret": SecretStr(TEST_CSRF_SECRET),
        "cors_allowed_origins": ("https://app.mti360.example",),
        "app_base_url": "https://app.mti360.example",
        "smtp_host": "smtp.mti360.example",
        "smtp_port": 587,
        "smtp_username": "mailer",
        "smtp_password": SecretStr("fake-smtp-password-7d1e"),
        "email_from_address": "no-reply@mti360.example",
        "ai_provider": "anthropic",
        "ai_provider_api_key": SecretStr("fake-ai-key-7d1e"),
    }


def build(env: str, **overrides: Any) -> Settings:
    values: dict[str, Any] = {"app_env": env}
    if env in DEPLOYED:
        values |= deployed_values()
    elif env == "test":
        values |= {
            "session_secret": SecretStr(TEST_SESSION_SECRET),
            "csrf_secret": SecretStr(TEST_CSRF_SECRET),
        }
    values |= overrides
    return load_settings(_env_file=None, **values)


def problems_for(env: str, **overrides: Any) -> str:
    with pytest.raises(ConfigurationError) as caught:
        build(env, **overrides)
    return str(caught.value)


# --- Valid baselines -----------------------------------------------------------------


def test_development_works_with_zero_configuration() -> None:
    settings = load_settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.ai_provider == "fake"
    assert settings.session_secret.get_secret_value() == "change-me"


def test_development_allows_debug_placeholders_and_fake_provider() -> None:
    settings = build("development", app_debug=True, log_level="DEBUG")

    assert settings.app_debug is True


@pytest.mark.parametrize("env", NON_DEVELOPMENT)
def test_valid_configuration_is_accepted(env: str) -> None:
    assert build(env).app_env == env


def test_test_environment_allows_the_fake_provider_and_defaults() -> None:
    settings = build("test")

    assert settings.ai_provider == "fake"
    assert settings.redis_url.get_secret_value() == "redis://localhost:6379/0"


# --- Rules for every environment ---------------------------------------------------


@pytest.mark.parametrize("env", ["development", *NON_DEVELOPMENT])
def test_wildcard_cors_origin_is_rejected(env: str) -> None:
    assert "CORS_ALLOWED_ORIGINS" in problems_for(env, cors_allowed_origins=("*",))


@pytest.mark.parametrize("env", ["development", *NON_DEVELOPMENT])
def test_database_urls_must_use_distinct_users(env: str) -> None:
    same_user = _db_url("mti_app")
    message = problems_for(env, migrations_database_url=same_user)

    assert "must each use a different database user" in message


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://mti_app:pw@localhost:5432/mti360",  # wrong driver
        "postgresql+asyncpg://localhost:5432/mti360",  # no user
        "postgresql+asyncpg://mti_app:pw@localhost:5432/",  # no database
        "postgresql+asyncpg://mti_app:pw@localhost:port/mti360",  # bad port
    ],
)
def test_malformed_database_url_is_rejected(url: str) -> None:
    assert "DATABASE_URL" in problems_for("development", database_url=SecretStr(url))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("redis_url", SecretStr("http://localhost:6379")),
        ("s3_endpoint_url", "ftp://storage.local"),
        ("cors_allowed_origins", ("https://app.example.com/path",)),
        ("email_from_address", "not-an-email"),
        ("ai_provider", "Not A Provider"),
        ("smtp_port", 70_000),
        ("s3_presigned_url_ttl_seconds", 0),
    ],
)
def test_malformed_values_are_rejected(field: str, value: Any) -> None:
    assert field.upper() in problems_for("development", **{field: value})


def test_idle_timeout_must_not_exceed_absolute_timeout() -> None:
    message = problems_for("development", platform_session_idle_timeout_minutes=500)

    assert "PLATFORM_SESSION_IDLE_TIMEOUT_MINUTES" in message


def test_cors_origins_are_parsed_from_a_comma_separated_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000, http://localhost:3100")

    settings = load_settings(_env_file=None)

    assert settings.cors_allowed_origins == ("http://localhost:3000", "http://localhost:3100")


# --- Test, staging and production -------------------------------------------------------


@pytest.mark.parametrize("env", NON_DEVELOPMENT)
def test_debug_is_rejected_outside_development(env: str) -> None:
    assert "APP_DEBUG" in problems_for(env, app_debug=True)


@pytest.mark.parametrize("env", NON_DEVELOPMENT)
@pytest.mark.parametrize("field", ["session_secret", "csrf_secret"])
@pytest.mark.parametrize("value", ["change-me", "", "x" * (MIN_SECRET_LENGTH - 1)])
def test_weak_session_secrets_are_rejected(env: str, field: str, value: str) -> None:
    assert field.upper() in problems_for(env, **{field: SecretStr(value)})


@pytest.mark.parametrize("env", NON_DEVELOPMENT)
def test_session_and_csrf_secrets_must_differ(env: str) -> None:
    message = problems_for(env, csrf_secret=SecretStr(TEST_SESSION_SECRET))

    assert "CSRF_SECRET: must differ from SESSION_SECRET" in message


def test_test_environment_requires_explicit_secrets() -> None:
    message = problems_for("test", session_secret=SecretStr("change-me"))

    assert "SESSION_SECRET" in message


# --- Staging and production ---------------------------------------------------------------


@pytest.mark.parametrize("env", DEPLOYED)
def test_fake_ai_provider_is_rejected(env: str) -> None:
    assert "AI_PROVIDER" in problems_for(env, ai_provider="fake")


@pytest.mark.parametrize("env", DEPLOYED)
@pytest.mark.parametrize(
    "field",
    [
        "s3_access_key_id",
        "s3_secret_access_key",
        "smtp_password",
        "ai_provider_api_key",
        "session_secret",
        "csrf_secret",
    ],
)
@pytest.mark.parametrize("value", ["change-me", "CHANGE-ME", ""])
def test_placeholder_secrets_are_rejected(env: str, field: str, value: str) -> None:
    assert field.upper() in problems_for(env, **{field: SecretStr(value)})


@pytest.mark.parametrize("env", DEPLOYED)
def test_infrastructure_settings_must_be_explicit(env: str) -> None:
    with pytest.raises(ConfigurationError) as caught:
        load_settings(_env_file=None, app_env=env)

    problems = "\n".join(caught.value.problems)
    for name in ("DATABASE_URL", "REDIS_URL", "S3_BUCKET", "SESSION_SECRET", "AI_PROVIDER"):
        assert f"{name}: must be set explicitly in {env}" in problems


@pytest.mark.parametrize("env", DEPLOYED)
@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (_db_url("mti_app", password="change-me"), "non-placeholder password"),
        (_db_url("mti_app", password=""), "non-placeholder password"),
        (_db_url("postgres"), "bootstrap superuser"),
        (_db_url("mti360_superuser"), "bootstrap superuser"),
        (_db_url("mti_app", query=""), "must require TLS"),
        (_db_url("mti_app", query="ssl=disable"), "must require TLS"),
        (_db_url("mti_app", query="ssl=prefer"), "must require TLS"),
    ],
)
def test_database_url_rules(env: str, url: SecretStr, expected: str) -> None:
    message = problems_for(env, database_url=url)

    assert "DATABASE_URL: must" in message
    assert expected in message


@pytest.mark.parametrize("env", DEPLOYED)
@pytest.mark.parametrize("mode", ["require", "verify-ca", "verify-full"])
def test_database_tls_modes_are_accepted(env: str, mode: str) -> None:
    settings = build(env, readonly_database_url=_db_url("mti_readonly", query=f"ssl={mode}"))

    assert settings.app_env == env


@pytest.mark.parametrize("env", DEPLOYED)
def test_cors_origins_must_use_https(env: str) -> None:
    message = problems_for(env, cors_allowed_origins=("http://app.mti360.example",))

    assert "CORS_ALLOWED_ORIGINS: every origin must use https" in message


@pytest.mark.parametrize("env", DEPLOYED)
def test_app_base_url_must_use_https(env: str) -> None:
    message = problems_for(env, app_base_url="http://app.mti360.example")

    assert "APP_BASE_URL: must use https" in message


@pytest.mark.parametrize(
    "value", ["app.mti360.example", "https://app.mti360.example/login", "https://u@host", "ftp://x"]
)
def test_app_base_url_must_be_an_origin(value: str) -> None:
    assert "APP_BASE_URL" in problems_for("development", app_base_url=value)


@pytest.mark.parametrize("env", DEPLOYED)
def test_s3_endpoint_must_use_https_when_set(env: str) -> None:
    assert "S3_ENDPOINT_URL" in problems_for(env, s3_endpoint_url="http://storage.internal")
    assert build(env, s3_endpoint_url="https://storage.internal").app_env == env


def test_debug_log_level_is_allowed_in_staging_only() -> None:
    assert build("staging", log_level="DEBUG").log_level == "DEBUG"
    assert "LOG_LEVEL" in problems_for("production", log_level="DEBUG")


def test_all_problems_are_reported_together() -> None:
    with pytest.raises(ConfigurationError) as caught:
        build("production", app_debug=True, ai_provider="fake", log_level="DEBUG")

    assert len(caught.value.problems) == 3


# --- Source policy: backend/.env is read in development only --------------------------------


# Weakening values plus one field that only this file sets.
DOTENV_CONTENT = "APP_DEBUG=true\nLOG_LEVEL=DEBUG\nS3_PRESIGNED_URL_TTL_SECONDS=999\n"


@pytest.fixture
def env_file(tmp_path: Path) -> Path:
    path = tmp_path / ".env"
    path.write_text(DOTENV_CONTENT, encoding="utf-8")
    return path


def test_development_reads_the_env_file(env_file: Path) -> None:
    settings = Settings(_env_file=env_file)

    assert settings.app_debug is True
    assert settings.log_level == "DEBUG"
    assert settings.s3_presigned_url_ttl_seconds == 999


@pytest.mark.parametrize("env", NON_DEVELOPMENT)
def test_non_development_environments_ignore_the_env_file(
    env: str, env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # APP_ENV comes from the process environment, as in a real deployment. The
    # fields the .env file sets are left out of the explicit values, so if the
    # file were read they would take effect (and break the production rules).
    monkeypatch.setenv("APP_ENV", env)
    omitted = {"app_env", "app_debug", "log_level", "s3_presigned_url_ttl_seconds"}
    values = {k: v for k, v in build(env).model_dump().items() if k not in omitted}

    settings = load_settings(_env_file=env_file, **values)

    assert settings.app_env == env
    assert settings.app_debug is False
    assert settings.log_level == "INFO"
    assert settings.s3_presigned_url_ttl_seconds == 300


@pytest.mark.parametrize("env", NON_DEVELOPMENT)
def test_env_file_cannot_select_the_environment(env: str, tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(f"APP_ENV={env}\n", encoding="utf-8")

    with pytest.raises(ConfigurationError) as caught:
        load_settings(_env_file=dotenv)

    assert "APP_ENV: must be set in the process environment" in str(caught.value)


# --- Secret masking ---------------------------------------------------------------------------

SENTINEL = "SENTINEL-7f3a91c2"


def _sentinel_secrets() -> dict[str, Any]:
    return {
        "database_url": _db_url("mti_app", password=SENTINEL, query=""),
        "redis_url": SecretStr(f"rediss://:{SENTINEL}@cache.internal:6380/0"),
        "s3_access_key_id": SecretStr(SENTINEL + "-id"),
        "s3_secret_access_key": SecretStr(SENTINEL + "-s3"),
        "session_secret": SecretStr(SENTINEL),  # too short: triggers a rule
        "csrf_secret": SecretStr(SENTINEL),  # equal: triggers a rule
        "smtp_password": SecretStr(SENTINEL + "-smtp"),
        "ai_provider_api_key": SecretStr(SENTINEL + "-ai"),
    }


def test_rule_errors_never_contain_secret_values() -> None:
    with pytest.raises(ConfigurationError) as caught:
        build("production", **_sentinel_secrets())

    assert caught.value.problems
    assert SENTINEL not in str(caught.value)
    assert SENTINEL not in repr(caught.value)


def test_validation_errors_never_contain_input_values() -> None:
    # Deliberately invalid types and formats carrying the sentinel.
    invalid: dict[str, Any] = {
        "database_url": SecretStr(f"mysql://root:{SENTINEL}@db/mti360"),
        "smtp_port": SENTINEL,
    }

    with pytest.raises(ConfigurationError) as caught:
        load_settings(_env_file=None, **invalid)
    assert SENTINEL not in str(caught.value)
    assert {p.split(":")[0] for p in caught.value.problems} == {"DATABASE_URL", "SMTP_PORT"}

    with pytest.raises(ValidationError) as raw:
        Settings(_env_file=None, **invalid)
    assert SENTINEL not in str(raw.value)


def test_environment_variable_values_never_appear_in_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SESSION_SECRET", SENTINEL)
    monkeypatch.setenv("SMTP_PORT", SENTINEL)

    with pytest.raises(ConfigurationError) as caught:
        load_settings(_env_file=None)

    assert SENTINEL not in str(caught.value)


def test_secrets_are_masked_in_repr_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    settings = build("development", **_sentinel_secrets() | {"csrf_secret": SecretStr("other")})

    with caplog.at_level(logging.INFO):
        logging.getLogger("mti360.test").info("settings: %s %r", settings, settings)

    for text in (repr(settings), str(settings), settings.model_dump_json(), caplog.text):
        assert SENTINEL not in text
