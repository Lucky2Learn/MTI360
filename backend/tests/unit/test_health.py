"""Toolchain smoke tests for the application factory and liveness endpoint (T00-02)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app

pytestmark = pytest.mark.anyio


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_api_docs_are_not_exposed_outside_development(client: AsyncClient) -> None:
    assert (await client.get("/docs")).status_code == 404
    assert (await client.get("/openapi.json")).status_code == 404


async def test_api_docs_are_exposed_in_development() -> None:
    app = create_app(Settings(_env_file=None, app_env="development"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        assert (await c.get("/docs")).status_code == 200
        assert (await c.get("/openapi.json")).status_code == 200
