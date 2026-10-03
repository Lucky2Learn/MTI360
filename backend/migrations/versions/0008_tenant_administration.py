# Policy SQL is assembled only from the constants below (no input): S608 is a false positive.
"""Tenant administration: invitee identities, tenant audit visibility, campus scope (T01-08).

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-03

Locked decisions D8-1 … D8-4 (docs/architecture/tenant-administration.md):

* **D8-1** ``users_insert`` gains one term: in the tenant realm, with a
  trusted tenant and an authenticated principal, a ``users`` row may be
  inserted only when its ``id`` equals ``app.tenant_invitee_user_id`` and its
  status is ``INVITED``. The key is published only by
  ``app.modules.identity.members`` after ``authorize()``; there is no
  tenant-realm-wide ``users`` INSERT.
* **D8-2** ``audit_events_tenant_read`` also requires the event's own realm to
  be ``tenant``: platform-written events (provisioning included) stay
  platform-only, whatever ``tenant_id`` they carry.
* **Campus scope** (``PUT /members/{id}/campus-scope``): T01-04 decision D16
  forbids DELETE on identity tables, so a campus leaving a member's selection
  is marked ``membership_campuses.removed_at`` instead. That needs UPDATE on
  ``membership_campuses`` (0004 granted SELECT, INSERT), under the table's own
  tenant rule (``tenant_id = app.tenant_id`` or the system realm). The
  downgrade deletes the removed rows first (as the owner), so it never turns a
  removed campus back into a permitted one.

The existing policies are altered in place (same names); the downgrade
restores the frozen 0002/0007 expressions. No SECURITY DEFINER.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.helpers import database_roles, quote_role

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies at this revision.
T = "nullif(current_setting('app.tenant_id', true), '')::uuid"
U = "nullif(current_setting('app.user_id', true), '')::uuid"
SYSTEM = "nullif(current_setting('app.realm', true), '') = 'system'"
PLATFORM = "nullif(current_setting('app.realm', true), '') = 'platform'"
TENANT = "nullif(current_setting('app.realm', true), '') = 'tenant'"
TRUSTED_REALM = "nullif(current_setting('app.realm', true), '')"
PROVISIONING = "nullif(current_setting('app.provisioning_tenant_id', true), '')::uuid"
# New in 0008 (D8-1).
INVITEE = "nullif(current_setting('app.tenant_invitee_user_id', true), '')::uuid"

PROVISIONED_OWNER = f"({PLATFORM} AND {PROVISIONING} = {T} AND status = 'INVITED')"
INVITED_IDENTITY = (
    f"({TENANT} AND {T} IS NOT NULL AND {U} IS NOT NULL AND id = {INVITEE} AND status = 'INVITED')"
)
USERS_INSERT_BEFORE = f"{SYSTEM} OR {PROVISIONED_OWNER}"
AUDIT_TENANT_READ_BEFORE = f"{TRUSTED_REALM} = 'tenant' AND tenant_id = {T}"
AUDIT_TENANT_READ = f"{TRUSTED_REALM} = 'tenant' AND realm = 'tenant' AND tenant_id = {T}"


def upgrade() -> None:
    app_role = quote_role(database_roles()["app"])
    op.execute(
        "ALTER POLICY users_insert ON users "
        f"WITH CHECK ({USERS_INSERT_BEFORE} OR {INVITED_IDENTITY})"
    )
    op.execute(f"ALTER POLICY audit_events_tenant_read ON audit_events USING ({AUDIT_TENANT_READ})")
    op.add_column(
        "membership_campuses",
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(f"GRANT UPDATE ON TABLE membership_campuses TO {app_role}")
    op.execute(
        "CREATE POLICY membership_campuses_update ON membership_campuses FOR UPDATE "
        f"TO {app_role} USING (tenant_id = {T} OR {SYSTEM}) "
        f"WITH CHECK (tenant_id = {T} OR {SYSTEM})"
    )


def downgrade() -> None:
    app_role = quote_role(database_roles()["app"])
    op.execute("DROP POLICY membership_campuses_update ON membership_campuses")
    op.execute(f"REVOKE UPDATE ON TABLE membership_campuses FROM {app_role}")
    # Before 0008 every row is a permitted campus: drop the removed ones, never re-grant them.
    op.execute("DELETE FROM membership_campuses WHERE removed_at IS NOT NULL")
    op.drop_column("membership_campuses", "removed_at")
    op.execute(
        f"ALTER POLICY audit_events_tenant_read ON audit_events USING ({AUDIT_TENANT_READ_BEFORE})"
    )
    op.execute(f"ALTER POLICY users_insert ON users WITH CHECK ({USERS_INSERT_BEFORE})")
