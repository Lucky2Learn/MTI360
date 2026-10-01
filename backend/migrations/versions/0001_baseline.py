"""Baseline: start the migration history and protect it (T01-01).

Revision ID: 0001
Revises:
Create Date: 2026-09-30

No application tables. The owner role creates ``alembic_version`` in this
first run, and the default privileges from ``database/init/01-roles.sh`` would
give the application role full DML on it. The runtime roles may read the
migration state (readiness checks) but must never change it.
"""

from collections.abc import Sequence

from alembic import op

from migrations.helpers import database_roles, quote_role

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    roles = database_roles()
    for role in (roles["app"], roles["readonly"]):
        op.execute(f"REVOKE ALL ON TABLE alembic_version FROM {quote_role(role)}")
        op.execute(f"GRANT SELECT ON TABLE alembic_version TO {quote_role(role)}")


def downgrade() -> None:
    # Restore the default privileges granted by database/init/01-roles.sh.
    roles = database_roles()
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE alembic_version "
        f"TO {quote_role(roles['app'])}"
    )
