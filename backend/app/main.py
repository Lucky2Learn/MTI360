"""FastAPI application factory.

Run locally (from ``backend/``)::

    uv run uvicorn app.main:create_app --factory --reload --port 8000 --no-access-log

(or ``pnpm dev:backend`` from the repository root).

Realm routers (``/api/v1/platform``, ``/api/v1``, ``/api/v1/student``,
``/api/v1/public``, ``/api/v1/webhooks`` — ADR-0006) are mounted with
deny-by-default guards (``app/api``); modules add their routes to them.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.api import mount_api, operation_id
from app.core.config import Settings, get_settings
from app.core.db import create_engine, create_sessionmaker
from app.core.errors import install_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.ratelimit import RedisRateLimiter
from app.integrations.email import SmtpEmailSender
from app.integrations.storage import S3ObjectStorage
from app.modules.identity.members import MemberAdmin
from app.modules.identity.passwords import PasswordHasher
from app.modules.identity.service import IdentityConfig, IdentityService
from app.modules.platform_identity.admin import PlatformUserAdmin
from app.modules.platform_identity.service import (
    RATE_LIMIT_NAMESPACE as PLATFORM_RATE_LIMIT_NAMESPACE,
)
from app.modules.platform_identity.service import (
    PlatformIdentityConfig,
    PlatformIdentityService,
)
from app.modules.tenants.service import TenantAdmin

UPLOAD_RATE_LIMIT_NAMESPACE = "uploads"
"""Redis key space of the document-upload limit (Phase 02-2; ADR-0021 §8)."""


class HealthResponse(BaseModel):
    """Liveness response. Deliberately reveals no version, environment or host detail."""

    status: Literal["ok"] = "ok"


def identity_config(settings: Settings) -> IdentityConfig:
    """Authentication settings (T01-04). Secrets stay inside the service."""
    return IdentityConfig(
        session_secret=settings.session_secret.get_secret_value(),
        csrf_secret=settings.csrf_secret.get_secret_value(),
        idle_timeout=timedelta(minutes=settings.session_idle_timeout_minutes),
        absolute_timeout=timedelta(minutes=settings.session_absolute_timeout_minutes),
        app_base_url=settings.app_base_url,
        allowed_origins=frozenset({*settings.cors_allowed_origins, settings.app_base_url}),
    )


def platform_identity_config(settings: Settings) -> PlatformIdentityConfig:
    """Platform authentication settings (T01-06): shorter sessions (ADR-0005)."""
    return PlatformIdentityConfig(
        session_secret=settings.session_secret.get_secret_value(),
        csrf_secret=settings.csrf_secret.get_secret_value(),
        idle_timeout=timedelta(minutes=settings.platform_session_idle_timeout_minutes),
        absolute_timeout=timedelta(minutes=settings.platform_session_absolute_timeout_minutes),
        app_base_url=settings.app_base_url,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application.

    Settings are loaded and validated here, before the server accepts requests:
    an invalid configuration raises ``ConfigurationError`` and the process exits
    (fail fast, T00-04). The error names variables and rules, never values.

    The database engine is created here but opens no connection until a request
    needs one; ``/health`` never touches the database.
    """
    settings = settings if settings is not None else get_settings()
    is_development = settings.app_env == "development"
    configure_logging(settings.log_level)

    engine = create_engine(settings)
    sessionmaker = create_sessionmaker(engine)
    # Neither client opens a connection before it is used (/health stays dependency-free).
    rate_limiter = RedisRateLimiter.from_url(settings.redis_url.get_secret_value())
    hasher = PasswordHasher(
        time_cost=settings.argon2_time_cost,
        memory_cost_kib=settings.argon2_memory_cost_kib,
        parallelism=settings.argon2_parallelism,
    )
    email_sender = SmtpEmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password.get_secret_value(),
        from_address=settings.email_from_address,
        timeout_seconds=settings.smtp_timeout_seconds,
    )
    keyring = settings.encryption_keyring()
    identity = IdentityService(
        factory=sessionmaker,
        config=identity_config(settings),
        hasher=hasher,
        rate_limiter=rate_limiter,
        email_sender=email_sender,
        keyring=keyring,
    )
    # A separate rate-limit namespace for the platform realm (T01-06).
    platform_identity = PlatformIdentityService(
        factory=sessionmaker,
        config=platform_identity_config(settings),
        hasher=hasher,
        rate_limiter=RedisRateLimiter.from_url(
            settings.redis_url.get_secret_value(), namespace=PLATFORM_RATE_LIMIT_NAMESPACE
        ),
        email_sender=email_sender,
        keyring=keyring,
    )

    # Platform administration (T01-07) builds on the platform identity service.
    platform_users = PlatformUserAdmin(platform_identity)
    tenant_admin = TenantAdmin(platform_identity, invitation_secret=identity.config.session_secret)
    # Tenant member administration (T01-08) builds on the identity service.
    members = MemberAdmin(identity)
    # Admission documents (Phase 02-2): private object storage and an upload rate limit.
    # Neither opens a connection before it is used.
    storage = S3ObjectStorage.create(
        endpoint_url=settings.s3_endpoint_url or None,
        region=settings.s3_region,
        bucket=settings.s3_bucket,
        access_key_id=settings.s3_access_key_id.get_secret_value(),
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
    )
    upload_limiter = RedisRateLimiter.from_url(
        settings.redis_url.get_secret_value(), namespace=UPLOAD_RATE_LIMIT_NAMESPACE
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await app.state.identity.rate_limiter.close()
        await app.state.platform_identity.rate_limiter.close()
        await app.state.upload_limiter.close()
        await engine.dispose()

    app = FastAPI(
        title="MTI 360 API",
        debug=settings.app_debug,
        # Interactive API documentation is exposed only in development.
        docs_url="/docs" if is_development else None,
        redoc_url=None,
        openapi_url="/openapi.json" if is_development else None,
        lifespan=lifespan,
        generate_unique_id_function=operation_id,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker
    app.state.identity = identity
    app.state.platform_identity = platform_identity
    app.state.platform_users = platform_users
    app.state.tenant_admin = tenant_admin
    app.state.members = members
    app.state.storage = storage
    app.state.upload_limiter = upload_limiter

    install_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    mount_api(app)

    @app.get("/health", tags=["operations"])
    async def health() -> HealthResponse:
        """Process liveness probe. Performs no dependency (database/cache) checks."""
        return HealthResponse()

    return app
