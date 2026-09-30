"""FastAPI application factory.

Run locally (from ``backend/``)::

    uv run uvicorn app.main:create_app --factory --reload --port 8000 --no-access-log

(or ``pnpm dev:backend`` from the repository root).

Realm routers (``/api/v1/platform``, ``/api/v1``, ``/api/v1/student``,
``/api/v1/public``, ``/api/v1/webhooks`` — ADR-0006) are mounted by later tasks.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.db import create_engine, create_sessionmaker
from app.core.errors import install_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware


class HealthResponse(BaseModel):
    """Liveness response. Deliberately reveals no version, environment or host detail."""

    status: Literal["ok"] = "ok"


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

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    app = FastAPI(
        title="MTI 360 API",
        debug=settings.app_debug,
        # Interactive API documentation is exposed only in development.
        docs_url="/docs" if is_development else None,
        redoc_url=None,
        openapi_url="/openapi.json" if is_development else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = create_sessionmaker(engine)

    install_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/health", tags=["operations"])
    async def health() -> HealthResponse:
        """Process liveness probe. Performs no dependency (database/cache) checks."""
        return HealthResponse()

    return app
