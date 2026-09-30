"""Helpers shared by migration scripts (T01-01)."""

from typing import TypedDict

from alembic import op
from sqlalchemy.sql.elements import quoted_name


class DatabaseRoles(TypedDict):
    """Runtime roles that receive grants (the owner runs the migrations)."""

    app: str
    readonly: str


def database_roles() -> DatabaseRoles:
    """Runtime role names resolved by ``env.py`` (from settings or test attributes)."""
    config = op.get_context().config
    if config is None:
        raise RuntimeError("database roles are only available inside migrations/env.py")
    roles: DatabaseRoles = config.attributes["database_roles"]
    if not roles["app"] or not roles["readonly"]:
        raise RuntimeError("application and read-only database roles must be known")
    return roles


def quote_role(name: str) -> str:
    """Quote a role name for use in GRANT / REVOKE statements."""
    return op.get_bind().dialect.identifier_preparer.quote(quoted_name(name, quote=True))
