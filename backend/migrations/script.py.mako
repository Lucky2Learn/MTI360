"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

Review checklist (backend-foundation.md §4, §13; ADR-0014): tenant-owned
tables use TenantScopedMixin and declare UNIQUE (tenant_id, id); children of
tenant-scoped parents use tenant_foreign_key(); RLS is enabled with the
realm-agnostic policy tenant_id = nullif(current_setting('app.tenant_id',
true), '')::uuid for USING and WITH CHECK (copied into the migration, never
imported); grants are explicit (REVOKE ALL first, no DELETE unless the task
requires it); the downgrade restores the previous state; no data is lost
silently.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
