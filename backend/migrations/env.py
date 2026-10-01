"""Alembic environment (T01-01): async, owner role, complete model metadata.

Connection URL, in order:

1. ``config.attributes["database_url"]`` — set programmatically (tests);
2. ``MIGRATIONS_DATABASE_URL`` from the validated backend settings.

The URL is never written to ``alembic.ini`` or logged. Settings are validated
exactly as for the API, so a migration run fails fast on invalid configuration.

The runtime role names (application and read-only) are taken from the user
part of ``DATABASE_URL`` / ``READONLY_DATABASE_URL`` — or from
``config.attributes["database_roles"]`` — and exposed to migrations through
:func:`migrations.helpers.database_roles` for grants and RLS.
"""

import asyncio
import importlib
import logging.config
import pkgutil
from urllib.parse import urlsplit

from alembic import context
from sqlalchemy import MetaData, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.modules
from app.core.config import load_settings
from app.core.db.base import Base

config = context.config

# Core packages that define tables (for example "app.core.audit.models").
CORE_MODEL_MODULES: tuple[str, ...] = ()


def load_all_models() -> MetaData:
    """Import every model module so that autogenerate sees the full schema."""
    for name in CORE_MODEL_MODULES:
        importlib.import_module(name)
    for module in pkgutil.iter_modules(app.modules.__path__, prefix="app.modules."):
        if not module.ispkg:
            continue
        try:
            importlib.import_module(f"{module.name}.models")
        except ModuleNotFoundError as error:
            if error.name != f"{module.name}.models":
                raise
    return Base.metadata


def _connection_settings() -> tuple[str, dict[str, str]]:
    url = config.attributes.get("database_url")
    roles = config.attributes.get("database_roles")
    if url is None or roles is None:
        settings = load_settings()
        url = url or settings.migrations_database_url.get_secret_value()
        roles = roles or {
            "app": urlsplit(settings.database_url.get_secret_value()).username or "",
            "readonly": urlsplit(settings.readonly_database_url.get_secret_value()).username or "",
        }
    return url, roles


if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    logging.config.fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = load_all_models()
database_url, database_roles = _connection_settings()
config.attributes["database_roles"] = database_roles


def _configure(**kwargs: object) -> None:
    context.configure(
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        transaction_per_migration=True,
        **kwargs,  # type: ignore[arg-type]
    )


def run_migrations_offline() -> None:
    """Emit SQL to stdout (``alembic upgrade head --sql``) for review."""
    _configure(url=database_url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection: Connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(database_url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run_sync)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
