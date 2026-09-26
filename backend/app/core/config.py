"""Application settings.

T00-02 reads only the runtime basics. Per-environment validation (for example,
refusing placeholder secrets in production) and the remaining settings are
added in T00-04 and later tasks. Unknown variables in ``backend/.env`` are
ignored so that templates can declare variables ahead of their first use.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

type AppEnv = Literal["development", "test", "staging", "production"]
type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and ``backend/.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_env: AppEnv = "development"
    # Secure default: debug must be enabled explicitly (local .env only).
    app_debug: bool = False
    log_level: LogLevel = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
