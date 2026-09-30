"""Async engine and session factory (T01-01; ADR-0001).

The API connects as the application role (``DATABASE_URL`` → ``mti_app``: DML
only, no ``BYPASSRLS``). Migrations use ``MIGRATIONS_DATABASE_URL`` (owner) and
never run through this engine. Creating the engine opens no connection; the
first connection is made by the first request that needs the database.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings

APPLICATION_NAME = "mti360-api"


def create_engine(settings: Settings) -> AsyncEngine:
    """Build the application-role engine from validated settings."""
    return create_async_engine(
        settings.database_url.get_secret_value(),
        # Detects connections dropped by the server or a network device.
        pool_pre_ping=True,
        # Never log SQL or bound parameters from the engine (they can contain
        # personal data); query diagnostics go through structured logging.
        echo=False,
        hide_parameters=True,
        connect_args={"server_settings": {"application_name": APPLICATION_NAME}},
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory: explicit transactions, no implicit refresh after commit."""
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=True)
