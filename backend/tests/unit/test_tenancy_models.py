"""Tenancy model conventions (T01-03; ADR-0014)."""

from typing import cast

from sqlalchemy import Column, ForeignKeyConstraint, MetaData, Table, UniqueConstraint, Uuid

from app.core.db.base import Base
from app.core.tenancy import TenantScopedMixin, tenant_foreign_key
from app.modules.institute.models import Campus
from app.modules.tenants.domain import INITIAL_STATUS, TenantStatus
from app.modules.tenants.models import Tenant


def _tenant_scoped_tables() -> list[Table]:
    return [
        cast(Table, mapper.local_table)
        for mapper in Base.registry.mappers
        if issubclass(mapper.class_, TenantScopedMixin)
    ]


def test_campuses_are_tenant_scoped_and_tenants_are_not() -> None:
    assert issubclass(Campus, TenantScopedMixin)
    assert not issubclass(Tenant, TenantScopedMixin)
    assert "campuses" in {table.name for table in _tenant_scoped_tables()}


def test_every_tenant_scoped_table_is_a_composite_foreign_key_target() -> None:
    for table in _tenant_scoped_tables():
        tenant_id = table.c.tenant_id
        targets = [
            [column.name for column in constraint.columns]
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        ]

        assert not tenant_id.nullable, table.name
        # tenant_id references tenants; it may also be part of composite keys
        # to tenant-scoped parents (tenant_foreign_key), always RESTRICT.
        assert "tenants.id" in [fk.target_fullname for fk in tenant_id.foreign_keys], table.name
        assert all(fk.ondelete == "RESTRICT" for fk in tenant_id.foreign_keys), table.name
        assert ["tenant_id", "id"] in targets, table.name


def test_tenant_foreign_key_references_the_parent_tenant_and_id() -> None:
    metadata = MetaData()
    Table("campuses", metadata, Column("tenant_id", Uuid), Column("id", Uuid))
    child = Table(
        "probe_batches",
        metadata,
        Column("tenant_id", Uuid),
        Column("campus_id", Uuid),
        tenant_foreign_key("campus_id", "campuses"),
    )
    (constraint,) = [c for c in child.constraints if isinstance(c, ForeignKeyConstraint)]

    assert constraint.column_keys == ["tenant_id", "campus_id"]
    assert [element.target_fullname for element in constraint.elements] == [
        "campuses.tenant_id",
        "campuses.id",
    ]
    assert constraint.ondelete == "RESTRICT"


def test_tenant_statuses_are_the_eight_lifecycle_states_and_new_tenants_start_in_trial() -> None:
    assert [status.value for status in TenantStatus] == [
        "PROSPECT",
        "TRIAL",
        "PROVISIONING",
        "ACTIVE",
        "PAST_DUE",
        "SUSPENDED",
        "CANCELLED",
        "DEACTIVATED",
    ]
    assert INITIAL_STATUS is TenantStatus.TRIAL
    assert Tenant(name="Probe Institute").status is None  # the default applies on insert
    assert cast(Table, Tenant.__table__).c.status.default.arg == "TRIAL"  # type: ignore[union-attr]
