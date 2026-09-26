"""Shared pytest fixtures.

Async tests use AnyIO's pytest plugin (``@pytest.mark.anyio``) on the asyncio
backend. Tests never read ``backend/.env`` (the ``test`` environment ignores it)
and every settings variable is removed from the process environment, so a
developer's local configuration cannot change test results. Test settings are
constructed from explicit values.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.main import create_app

# Fixed, non-placeholder test values (>= 32 characters, distinct). Not real secrets.
TEST_SESSION_SECRET = "mti360-test-session-secret-0123456789abcdef"
TEST_CSRF_SECRET = "mti360-test-csrf-secret-0123456789abcdef"


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    get_settings.cache_clear()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        session_secret=SecretStr(TEST_SESSION_SECRET),
        csrf_secret=SecretStr(TEST_CSRF_SECRET),
    )


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    return create_app(test_settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c
