"""Application settings and per-environment validation (T00-04).

Every variable declared in ``backend/.env.example`` is typed here. The four
environments (``development``, ``test``, ``staging``, ``production``) share one
settings class; the rules that differ between them are enforced when the
settings are built, so an invalid configuration fails fast at startup.

Where values come from:

* development: ``backend/.env`` (optional) and the process environment. Every
  field has a local default matching the T00-03 infrastructure, so development
  works with zero configuration.
* test: explicit values only (constructor arguments and the process
  environment). ``backend/.env`` is never read.
* staging / production: the process environment only (populated by the secret
  manager). ``backend/.env`` is never read, and infrastructure settings must be
  set explicitly rather than falling back to the local defaults.

Secret values are ``SecretStr`` and never appear in ``repr``, logs or error
messages: validation errors hide their input, and :class:`ConfigurationError`
lists only variable names and the rules they broke.

The environment matrix is documented in ``docs/architecture/environments.md``.
"""

import re
from collections.abc import Iterable
from functools import lru_cache
from typing import Annotated, Any, Literal, Self
from urllib.parse import parse_qs, unquote, urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

type AppEnv = Literal["development", "test", "staging", "production"]
type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

DEPLOYED_ENVIRONMENTS: frozenset[str] = frozenset({"staging", "production"})
"""Environments that run on shared infrastructure with secret-manager values."""

MIN_SECRET_LENGTH = 32
"""Minimum length of ``SESSION_SECRET`` and ``CSRF_SECRET`` outside development."""

PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    {"change-me", "changeme", "change_me", "replace-me", "placeholder", "secret", "password"}
)
"""Template values that must never be used as a real secret (compared case-insensitively)."""

DATABASE_DRIVER = "postgresql+asyncpg"
DATABASE_TLS_MODES: frozenset[str] = frozenset({"require", "verify-ca", "verify-full"})
# Bootstrap superusers (the upstream image default and the local T00-03 name).
# The application, migrations and read-only access must use dedicated roles.
RESERVED_DATABASE_USERS: frozenset[str] = frozenset({"postgres", "mti360_superuser"})

_AI_PROVIDER_PATTERN = r"^[a-z][a-z0-9_-]*$"
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Settings that staging and production must set explicitly. Their defaults point
# at the local development infrastructure and must never be used silently.
_EXPLICIT_IN_DEPLOYED: tuple[str, ...] = (
    "database_url",
    "migrations_database_url",
    "readonly_database_url",
    "redis_url",
    "s3_endpoint_url",
    "s3_region",
    "s3_bucket",
    "s3_access_key_id",
    "s3_secret_access_key",
    "session_secret",
    "csrf_secret",
    "cors_allowed_origins",
    "smtp_host",
    "smtp_port",
    "smtp_username",
    "smtp_password",
    "email_from_address",
    "ai_provider",
    "ai_provider_api_key",
)

# Plain secrets that staging and production must set to a real (non-empty,
# non-placeholder) value. Database passwords are checked inside their URLs.
_SECRETS_IN_DEPLOYED: tuple[str, ...] = (
    "s3_access_key_id",
    "s3_secret_access_key",
    "session_secret",
    "csrf_secret",
    "smtp_password",
    "ai_provider_api_key",
)

_DATABASE_URL_FIELDS: tuple[str, ...] = (
    "database_url",
    "migrations_database_url",
    "readonly_database_url",
)


class ConfigurationError(Exception):
    """Raised when settings are invalid for the selected environment.

    The message names variables and broken rules only; it never contains values.
    """

    def __init__(self, problems: Iterable[str]) -> None:
        self.problems: tuple[str, ...] = tuple(problems)
        lines = "\n".join(f"  - {problem}" for problem in self.problems)
        super().__init__(f"Invalid configuration:\n{lines}")

    @classmethod
    def from_validation_error(cls, error: ValidationError) -> ConfigurationError:
        """Convert a pydantic error into a value-free configuration error."""
        problems = []
        for detail in error.errors(include_url=False, include_context=False, include_input=False):
            name = _env_name(str(detail["loc"][0])) if detail["loc"] else "SETTINGS"
            problems.append(f"{name}: {detail['msg']}")
        return cls(problems)


def _env_name(field_name: str) -> str:
    return field_name.upper()


def is_placeholder(value: str) -> bool:
    """Return True for empty values and template placeholders such as ``change-me``."""
    normalized = value.strip().lower()
    return not normalized or normalized in PLACEHOLDER_VALUES


class _DevelopmentDotEnvSource(PydanticBaseSettingsSource):
    """Reads ``backend/.env`` only when the resolved environment is development.

    ``APP_ENV`` itself is resolved from constructor arguments and the process
    environment only, so a ``.env`` file can never switch a process into, or
    out of, a deployed environment.
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        dotenv_source: PydanticBaseSettingsSource,
        app_env: str,
    ) -> None:
        super().__init__(settings_cls)
        self._dotenv_source = dotenv_source
        self._app_env = app_env

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        # Values are produced in bulk by __call__.
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        if self._app_env != "development":
            return {}
        values = self._dotenv_source()
        if values.get("app_env", "development") != "development":
            raise ConfigurationError(
                ["APP_ENV: must be set in the process environment, not in backend/.env"]
            )
        return values


class Settings(BaseSettings):
    """Typed runtime settings. See the module docstring for the source policy."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    # --- Runtime ---------------------------------------------------------------
    app_env: AppEnv = "development"
    # Secure default: debug must be enabled explicitly (development only).
    app_debug: bool = False
    log_level: LogLevel = "INFO"

    # --- PostgreSQL (T00-03 roles; ADR-0004) -----------------------------------------
    # Validated only: no engine or connection exists yet.
    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://mti_app:change-me@localhost:5432/mti360"
    )
    migrations_database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://mti_owner:change-me@localhost:5432/mti360"
    )
    readonly_database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://mti_readonly:change-me@localhost:5432/mti360"
    )

    # --- Redis (the URL may carry a password) -------------------------------------------
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")

    # --- Object storage (S3-compatible) -------------------------------------------------
    # Empty endpoint = the provider's default endpoint.
    s3_endpoint_url: str = "http://127.0.0.1:8333"
    s3_region: str = Field(default="us-east-1", min_length=1)
    s3_bucket: str = Field(default="mti360-local", min_length=1)
    s3_access_key_id: SecretStr = SecretStr("change-me")
    s3_secret_access_key: SecretStr = SecretStr("change-me")
    # Upper bound is the S3 maximum for presigned URLs (7 days).
    s3_presigned_url_ttl_seconds: int = Field(default=300, gt=0, le=604_800)

    # --- Sessions and CSRF (ADR-0005). Validated only: no session code yet. ---------------
    session_secret: SecretStr = SecretStr("change-me")
    csrf_secret: SecretStr = SecretStr("change-me")
    session_idle_timeout_minutes: int = Field(default=30, gt=0)
    session_absolute_timeout_minutes: int = Field(default=720, gt=0)
    platform_session_idle_timeout_minutes: int = Field(default=15, gt=0)
    platform_session_absolute_timeout_minutes: int = Field(default=240, gt=0)
    # Comma-separated in the environment. Validated only: no CORS middleware yet.
    cors_allowed_origins: Annotated[tuple[str, ...], NoDecode] = ("http://localhost:3000",)

    # --- Email ---------------------------------------------------------------------------
    smtp_host: str = Field(default="localhost", min_length=1)
    smtp_port: int = Field(default=1025, gt=0, le=65_535)
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    email_from_address: str = "no-reply@mti360.local"

    # --- AI provider (CLAUDE.md §46) ----------------------------------------------------
    # `fake` is the deterministic provider for development and tests.
    ai_provider: str = Field(default="fake", pattern=_AI_PROVIDER_PATTERN)
    ai_provider_api_key: SecretStr = SecretStr("")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        app_env = init_settings().get("app_env") or env_settings().get("app_env") or "development"
        return (
            init_settings,
            env_settings,
            _DevelopmentDotEnvSource(settings_cls, dotenv_settings, str(app_env)),
            file_secret_settings,
        )

    # --- Field formats (all environments) -------------------------------------------------

    @field_validator(*_DATABASE_URL_FIELDS)
    @classmethod
    def _check_database_url(cls, value: SecretStr) -> SecretStr:
        parts = urlsplit(value.get_secret_value())
        try:
            parts.port  # noqa: B018 - accessing .port validates it
        except ValueError:
            raise ValueError("port must be a number") from None
        if parts.scheme != DATABASE_DRIVER:
            raise ValueError(f"must use the {DATABASE_DRIVER} driver")
        if not parts.username or not parts.hostname or not parts.path.strip("/"):
            raise ValueError("must include a user, host and database name")
        return value

    @field_validator("redis_url")
    @classmethod
    def _check_redis_url(cls, value: SecretStr) -> SecretStr:
        parts = urlsplit(value.get_secret_value())
        if parts.scheme not in {"redis", "rediss"} or not parts.hostname:
            raise ValueError("must be a redis:// or rediss:// URL with a host")
        return value

    @field_validator("s3_endpoint_url")
    @classmethod
    def _check_s3_endpoint_url(cls, value: str) -> str:
        if value:
            parts = urlsplit(value)
            if parts.scheme not in {"http", "https"} or not parts.hostname:
                raise ValueError("must be empty or an http(s) URL")
        return value

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_cors_allowed_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(origin.strip() for origin in value.split(",") if origin.strip())
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def _check_cors_allowed_origins(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for origin in value:
            if "*" in origin:
                raise ValueError("wildcard origins are not allowed")
            parts = urlsplit(origin)
            if (
                parts.scheme not in {"http", "https"}
                or not parts.hostname
                or parts.username is not None
                or parts.path
                or parts.query
                or parts.fragment
            ):
                raise ValueError("each entry must be an origin such as https://app.example.com")
        return value

    @field_validator("email_from_address")
    @classmethod
    def _check_email_from_address(cls, value: str) -> str:
        if not _EMAIL_PATTERN.match(value):
            raise ValueError("must be an email address")
        return value

    # --- Environment rules -------------------------------------------------------------

    @model_validator(mode="after")
    def _enforce_environment_rules(self) -> Self:
        problems = self._environment_problems()
        if problems:
            # Not a ValueError, so pydantic propagates it unchanged.
            raise ConfigurationError(problems)
        return self

    def _environment_problems(self) -> list[str]:
        env = self.app_env
        deployed = env in DEPLOYED_ENVIRONMENTS
        problems: list[str] = []

        # All environments.
        users = {name: self._database_user(name) for name in _DATABASE_URL_FIELDS}
        if len(set(users.values())) != len(users):
            problems.append(
                "DATABASE_URL, MIGRATIONS_DATABASE_URL, READONLY_DATABASE_URL: "
                "must each use a different database user"
            )
        for prefix in ("session", "platform_session"):
            idle = getattr(self, f"{prefix}_idle_timeout_minutes")
            absolute = getattr(self, f"{prefix}_absolute_timeout_minutes")
            if idle > absolute:
                problems.append(
                    f"{_env_name(prefix)}_IDLE_TIMEOUT_MINUTES: must not exceed "
                    f"{_env_name(prefix)}_ABSOLUTE_TIMEOUT_MINUTES"
                )

        # Test, staging and production.
        if env != "development":
            if self.app_debug:
                problems.append(f"APP_DEBUG: must be false in {env}")
            for name in ("session_secret", "csrf_secret"):
                secret = self._secret(name)
                if is_placeholder(secret) or len(secret) < MIN_SECRET_LENGTH:
                    problems.append(
                        f"{_env_name(name)}: must be a non-placeholder value of at least "
                        f"{MIN_SECRET_LENGTH} characters in {env}"
                    )
            if self._secret("session_secret") == self._secret("csrf_secret"):
                problems.append("CSRF_SECRET: must differ from SESSION_SECRET")

        # Staging and production.
        if deployed:
            missing = [name for name in _EXPLICIT_IN_DEPLOYED if name not in self.model_fields_set]
            problems.extend(
                f"{_env_name(name)}: must be set explicitly in {env}" for name in missing
            )
            problems.extend(
                f"{_env_name(name)}: must be set to a non-placeholder value in {env}"
                for name in _SECRETS_IN_DEPLOYED
                if name not in missing and is_placeholder(self._secret(name))
            )
            if self.ai_provider == "fake":
                problems.append(f"AI_PROVIDER: the fake provider is not allowed in {env}")
            for name in _DATABASE_URL_FIELDS:
                problems.extend(self._deployed_database_problems(name, env))
            for origin in self.cors_allowed_origins:
                if not origin.startswith("https://"):
                    problems.append(f"CORS_ALLOWED_ORIGINS: every origin must use https in {env}")
                    break
            if self.s3_endpoint_url and not self.s3_endpoint_url.startswith("https://"):
                problems.append(f"S3_ENDPOINT_URL: must be empty or use https in {env}")

        # Production only.
        if env == "production" and self.log_level == "DEBUG":
            problems.append("LOG_LEVEL: DEBUG is not allowed in production")

        return problems

    def _deployed_database_problems(self, name: str, env: str) -> list[str]:
        parts = urlsplit(self._secret(name))
        problems = []
        if is_placeholder(unquote(parts.password or "")):
            problems.append(f"{_env_name(name)}: must include a non-placeholder password in {env}")
        if parts.username in RESERVED_DATABASE_USERS:
            problems.append(f"{_env_name(name)}: must not use a bootstrap superuser in {env}")
        tls_modes = parse_qs(parts.query).get("ssl", [])
        if not tls_modes or tls_modes[-1] not in DATABASE_TLS_MODES:
            problems.append(
                f"{_env_name(name)}: must require TLS (ssl=require or stricter) in {env}"
            )
        return problems

    def _database_user(self, name: str) -> str:
        return urlsplit(self._secret(name)).username or ""

    def _secret(self, name: str) -> str:
        value: SecretStr = getattr(self, name)
        return value.get_secret_value()


def load_settings(**overrides: Any) -> Settings:
    """Build and validate settings, raising :class:`ConfigurationError` on any problem."""
    try:
        return Settings(**overrides)
    except ValidationError as error:
        raise ConfigurationError.from_validation_error(error) from None


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (validated on first use)."""
    return load_settings()
