"""API conventions through real realm routers (T01-01; ARCHITECTURE.md §36).

Envelope, error codes, validation details, request IDs, API headers,
pagination and sorting, OpenAPI operation IDs.
"""

import logging
import uuid

import pytest
from conftest import build_probe_app
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.context import optional_context

pytestmark = pytest.mark.anyio

PROBE = "/api/v1/public/probe"


def _error(response_json: dict[str, object]) -> dict[str, object]:
    error = response_json["error"]
    assert isinstance(error, dict)
    assert set(error) == {"code", "message", "details", "request_id"}
    return error


async def test_success_envelope_and_request_context(probe_client: AsyncClient) -> None:
    response = await probe_client.get(f"{PROBE}/context")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"data", "meta"}
    assert body["data"]["realm"] == "public"
    # The context carries the same correlation ID that is returned to the client.
    assert body["data"]["request_id"] == response.headers["X-Request-ID"]
    assert uuid.UUID(response.headers["X-Request-ID"]).version == 7


async def test_request_ids_are_unique_and_inbound_values_are_ignored(
    probe_client: AsyncClient,
) -> None:
    forged = "00000000-0000-7000-8000-000000000000"
    first = await probe_client.get(f"{PROBE}/context", headers={"X-Request-ID": forged})
    second = await probe_client.get(f"{PROBE}/context")

    assert first.headers["X-Request-ID"] != forged
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


async def test_api_responses_are_not_cached_or_sniffed(probe_client: AsyncClient) -> None:
    for path in (f"{PROBE}/context", "/api/v1/unknown"):
        response = await probe_client.get(path)
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    health = await probe_client.get("/health")
    assert "Cache-Control" not in health.headers
    assert "X-Request-ID" in health.headers


@pytest.mark.parametrize(
    ("kind", "status", "code"),
    [
        ("validation", 422, "VALIDATION_ERROR"),
        ("authentication", 401, "AUTHENTICATION_REQUIRED"),
        ("permission", 403, "PERMISSION_DENIED"),
        ("not_found", 404, "NOT_FOUND"),
        ("conflict", 409, "CONFLICT"),
        ("rate_limited", 429, "RATE_LIMITED"),
        ("stale", 409, "CONFLICT"),
    ],
)
async def test_application_errors_use_the_envelope(
    probe_client: AsyncClient, kind: str, status: int, code: str
) -> None:
    response = await probe_client.get(f"{PROBE}/errors/{kind}")

    assert response.status_code == status
    error = _error(response.json())
    assert error["code"] == code
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert error["message"]
    # Optimistic-locking internals (table names, statements) are not exposed.
    assert "probe" not in str(error["message"]).lower()


async def test_unexpected_errors_are_generic_logged_and_correlated(
    probe_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.errors"):
        response = await probe_client.get(f"{PROBE}/errors/unexpected")

    assert response.status_code == 500
    error = _error(response.json())
    assert error["code"] == "INTERNAL_ERROR"
    assert "SELECT" not in response.text
    assert "vault" not in response.text
    assert "Traceback" not in response.text
    assert response.headers["X-Request-ID"] == error["request_id"]
    logged = [r for r in caplog.records if r.getMessage() == "request.unhandled_exception"]
    assert len(logged) == 1
    assert logged[0].request_id == error["request_id"]  # type: ignore[attr-defined]
    assert logged[0].exc_info is not None


async def test_unknown_routes_and_methods(probe_client: AsyncClient) -> None:
    missing = await probe_client.get("/api/v1/no-such-resource")
    assert missing.status_code == 404
    assert _error(missing.json())["code"] == "NOT_FOUND"

    wrong_method = await probe_client.delete(f"{PROBE}/context")
    assert wrong_method.status_code == 405
    assert _error(wrong_method.json())["code"] == "METHOD_NOT_ALLOWED"


async def test_validation_errors_list_fields_without_echoing_input(
    probe_client: AsyncClient,
) -> None:
    foreign_tenant = "0199aaaa-bbbb-7ccc-8ddd-eeeeeeeeeeee"
    response = await probe_client.post(
        f"{PROBE}/items",
        json={"name": "Deck Cadet", "count": "not-a-number", "tenant_id": foreign_tenant},
    )

    assert response.status_code == 422
    error = _error(response.json())
    assert error["code"] == "VALIDATION_ERROR"
    details = error["details"]
    assert isinstance(details, list)
    by_field = {detail["field"]: detail for detail in details}
    assert by_field["count"]["code"] == "int_parsing"
    assert by_field["tenant_id"]["code"] == "extra_forbidden"
    assert "not-a-number" not in response.text
    assert foreign_tenant not in response.text


async def test_pagination_and_sorting(probe_client: AsyncClient) -> None:
    response = await probe_client.get(f"{PROBE}/rows", params={"sort": "-created_at,name"})

    assert response.status_code == 200
    body = response.json()
    assert [row["name"] for row in body["data"]] == ["-created_at", "name"]
    assert body["meta"]["page"] == {"limit": 25, "offset": 0, "total": 2}


@pytest.mark.parametrize(
    "params",
    [
        {"limit": "0"},
        {"limit": "101"},
        {"offset": "-1"},
        {"offset": "10001"},
        {"sort": "password_hash"},
        {"sort": "name,name"},
    ],
)
async def test_invalid_pagination_or_sort_is_rejected(
    probe_client: AsyncClient, params: dict[str, str]
) -> None:
    response = await probe_client.get(f"{PROBE}/rows", params=params)

    assert response.status_code == 422
    assert _error(response.json())["code"] == "VALIDATION_ERROR"
    assert "password_hash" not in response.text


async def test_openapi_uses_operation_ids_and_documents_the_error_envelope() -> None:
    app: FastAPI = build_probe_app(Settings(_env_file=None, app_env="development"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        schema = (await client.get("/openapi.json")).json()

    operation = schema["paths"]["/api/v1/public/probe/rows"]["get"]
    assert operation["operationId"] == "public_probe_probe_rows"
    assert schema["paths"]["/health"]["get"]["operationId"] == "operations_health"
    assert (
        schema["paths"]["/api/v1/platform/probe/protected"]["get"]["operationId"]
        == "platform_probe_probe_protected"
    )
    for status in ("401", "403", "404", "422", "500"):
        assert operation["responses"][status]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorEnvelope"
        }


async def test_the_request_context_ends_with_the_request(probe_client: AsyncClient) -> None:
    response = await probe_client.get("/api/v1/public/probe/context")

    assert response.status_code == 200
    assert optional_context() is None
