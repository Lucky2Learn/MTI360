"""Outbox: UNIQUE (tenant_id, id), like every tenant-scoped table (Phase 02-4).

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-01

ADR-0024. Every tenant-scoped table is a composite foreign-key target
(``tenancy.md``; ``tests/unit/test_tenancy_models.py``); ``0012`` created
``outbox_messages`` without that key. ``id`` is the primary key, so existing
rows always satisfy it: the upgrade only adds the constraint and its index.
The downgrade drops them. No data changes in either direction.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        op.f("uq_outbox_messages_tenant_id_id"), "outbox_messages", ["tenant_id", "id"]
    )


def downgrade() -> None:
    op.drop_constraint(op.f("uq_outbox_messages_tenant_id_id"), "outbox_messages", type_="unique")
