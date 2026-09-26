"""Shared pytest fixtures.

Async tests use AnyIO's pytest plugin (``@pytest.mark.anyio``) on the asyncio
backend. Tests never read ``backend/.env``: settings are constructed explicitly
so that a developer's local environment cannot change test results.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def test_settings() -> Settings:
    return Settings(_env_file=None, app_env="test")


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    return create_app(test_settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c
