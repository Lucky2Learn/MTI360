"""FastAPI application factory.

Run locally (from ``backend/``)::

    uv run uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000

Realm routers (``/api/v1/platform``, ``/api/v1``, ``/api/v1/student``,
``/api/v1/public``, ``/api/v1/webhooks`` — ADR-0006) are mounted by later tasks.
"""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.core.config import Settings, get_settings


class HealthResponse(BaseModel):
    """Liveness response. Deliberately reveals no version, environment or host detail."""

    status: Literal["ok"] = "ok"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application."""
    settings = settings or get_settings()
    is_development = settings.app_env == "development"

    app = FastAPI(
        title="MTI 360 API",
        debug=settings.app_debug,
        # Interactive API documentation is exposed only in development.
        docs_url="/docs" if is_development else None,
        redoc_url=None,
        openapi_url="/openapi.json" if is_development else None,
    )

    @app.get("/health", tags=["operations"])
    async def health() -> HealthResponse:
        """Process liveness probe. Performs no dependency (database/cache) checks."""
        return HealthResponse()

    return app
