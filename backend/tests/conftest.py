"""Shared pytest fixtures.

Async tests use AnyIO's pytest plugin (``@pytest.mark.anyio``) on the asyncio
backend. Tests never read ``backend/.env`` (the ``test`` environment ignores it)
and every settings variable is removed from the process environment, so a
developer's local configuration cannot change test results. Test settings are
constructed from explicit values.

Database tests (T01-01, ``@pytest.mark.integration``) run against a real
PostgreSQL test database — never SQLite — whose URLs come from
``TEST_DATABASE_URL``, ``TEST_MIGRATIONS_DATABASE_URL`` and
``TEST_READONLY_DATABASE_URL``. Without them the tests are skipped, unless
``REQUIRE_DATABASE_TESTS=1`` (CI), which turns the skip into a failure. See
docs/runbooks/local-development.md.

The probe application mounts test-only routes through the real realm routers
(``app.api.realms``), so guards, context, envelope and pagination are exercised
exactly as production routes will use them.
"""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

import pytest
from alembic.config import Config
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import Field, SecretStr
from sqlalchemy.orm.exc import StaleDataError

from app.api.realms import REALM_PREFIXES, Access, realm_router
from app.core.config import Settings, get_settings
from app.core.context import Realm, current_context
from app.core.errors import (
    AuthenticationRequiredError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitedError,
    ValidationFailedError,
)
from app.core.pagination import Pagination, SortField, sort_param
from app.core.schemas import Envelope, ListEnvelope, RequestModel, ResponseModel
from app.main import create_app

# Fixed, non-placeholder test values (>= 32 characters, distinct). Not real secrets.
TEST_SESSION_SECRET = "mti360-test-session-secret-0123456789abcdef"
TEST_CSRF_SECRET = "mti360-test-csrf-secret-0123456789abcdef"

BACKEND_DIR = Path(__file__).resolve().parents[1]


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


# --- Probe application (API conventions and realm guards) ---------------------------

PROBE_ERRORS: dict[str, Exception] = {
    "validation": ValidationFailedError(),
    "authentication": AuthenticationRequiredError(),
    "permission": PermissionDeniedError(),
    "not_found": NotFoundError(),
    "conflict": ConflictError(),
    "rate_limited": RateLimitedError(),
    "stale": StaleDataError("UPDATE statement on table 'probe' expected to update 1 row"),
    "unexpected": RuntimeError("internal detail: SELECT secret FROM vault"),
}
GUARDED_REALMS = (Realm.PLATFORM, Realm.TENANT, Realm.STUDENT, Realm.WEBHOOK)


class ProbeItem(RequestModel):
    name: str = Field(min_length=1, max_length=50)
    count: int = Field(ge=0)


class ProbeContext(ResponseModel):
    realm: str
    request_id: str


class ProbeRow(ResponseModel):
    name: str


def build_probe_app(settings: Settings) -> FastAPI:
    app = create_app(settings)

    public = realm_router(Realm.PUBLIC, access=Access.ANONYMOUS)

    @public.get("/probe/context", tags=["probe"])
    async def probe_context() -> Envelope[ProbeContext]:
        context = current_context()
        return Envelope(
            data=ProbeContext(realm=context.realm.value, request_id=str(context.request_id))
        )

    @public.get("/probe/rows", tags=["probe"])
    async def probe_rows(
        pagination: Pagination,
        sort: Annotated[
            tuple[SortField, ...],
            Depends(sort_param(allowed={"name", "created_at"}, default="name")),
        ],
    ) -> ListEnvelope[ProbeRow]:
        names = [f"{'-' if field.descending else ''}{field.name}" for field in sort]
        return ListEnvelope.build(
            [ProbeRow(name=name) for name in names],
            total=len(names),
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @public.post("/probe/items", tags=["probe"])
    async def probe_create(item: ProbeItem) -> Envelope[ProbeItem]:
        return Envelope(data=item)

    @public.get("/probe/errors/{kind}", tags=["probe"])
    async def probe_error(kind: str) -> None:
        raise PROBE_ERRORS[kind]

    app.include_router(public, prefix=REALM_PREFIXES[Realm.PUBLIC])

    for realm in GUARDED_REALMS:
        guarded = realm_router(realm)

        @guarded.get("/probe/protected", tags=["probe"])
        async def probe_protected() -> Envelope[ProbeContext]:  # pragma: no cover - denied
            raise AssertionError("a guarded handler must not run")

        @guarded.post("/probe/protected", tags=["probe"])
        async def probe_protected_write(
            item: ProbeItem,
        ) -> Envelope[ProbeItem]:  # pragma: no cover - denied
            raise AssertionError("a guarded handler must not run")

        app.include_router(guarded, prefix=REALM_PREFIXES[realm])

    return app


@pytest.fixture
def probe_app(test_settings: Settings) -> FastAPI:
    return build_probe_app(test_settings)


@pytest.fixture
async def probe_client(probe_app: FastAPI) -> AsyncIterator[AsyncClient]:
    # Unhandled exceptions become the 500 envelope instead of propagating.
    transport = ASGITransport(app=probe_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# --- PostgreSQL test database ---------------------------------------------------------


@dataclass(frozen=True)
class DatabaseUnderTest:
    app_url: str
    owner_url: str
    readonly_url: str

    @property
    def roles(self) -> dict[str, str]:
        return {
            "app": urlsplit(self.app_url).username or "",
            "readonly": urlsplit(self.readonly_url).username or "",
        }

    def settings(self) -> Settings:
        return Settings(
            _env_file=None,
            app_env="test",
            session_secret=SecretStr(TEST_SESSION_SECRET),
            csrf_secret=SecretStr(TEST_CSRF_SECRET),
            database_url=SecretStr(self.app_url),
            migrations_database_url=SecretStr(self.owner_url),
            readonly_database_url=SecretStr(self.readonly_url),
        )

    def alembic_config(self) -> Config:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.attributes["database_url"] = self.owner_url
        config.attributes["database_roles"] = self.roles
        config.attributes["configure_logging"] = False
        return config


_DATABASE_VARIABLES = (
    "TEST_DATABASE_URL",
    "TEST_MIGRATIONS_DATABASE_URL",
    "TEST_READONLY_DATABASE_URL",
)


@pytest.fixture(scope="session")
def test_database() -> DatabaseUnderTest:
    values = {name: os.environ.get(name, "") for name in _DATABASE_VARIABLES}
    missing = [name for name, value in values.items() if not value]
    if missing:
        message = (
            "PostgreSQL test database not configured (set "
            + ", ".join(missing)
            + "; see docs/runbooks/local-development.md)"
        )
        if os.environ.get("REQUIRE_DATABASE_TESTS") == "1":
            pytest.fail(message)
        pytest.skip(message)
    return DatabaseUnderTest(
        app_url=values["TEST_DATABASE_URL"],
        owner_url=values["TEST_MIGRATIONS_DATABASE_URL"],
        readonly_url=values["TEST_READONLY_DATABASE_URL"],
    )


@pytest.fixture(scope="session")
def migrated_database(test_database: DatabaseUnderTest) -> DatabaseUnderTest:
    """The test database at the latest migration (applied once per session)."""
    from alembic import command

    command.upgrade(test_database.alembic_config(), "head")
    return test_database
