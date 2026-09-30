"""Identifier and model conventions (T01-01)."""

import uuid
from typing import cast

from sqlalchemy import DateTime, MetaData, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.db import (
    NAMING_CONVENTION,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    VersionedMixin,
)
from app.core.ids import new_id


class _ProbeBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class _Vessel(UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, _ProbeBase):
    __tablename__ = "probe_vessels"

    name: Mapped[str] = mapped_column(unique=True)


def test_new_id_is_uuid7_and_time_ordered() -> None:
    ids = [new_id() for _ in range(100)]

    assert all(value.version == 7 for value in ids)
    assert len(set(ids)) == 100
    assert ids == sorted(ids)


def test_mixins_define_primary_key_timestamps_and_version() -> None:
    table = _Vessel.__table__
    columns = list(table.columns.keys())

    assert columns[0] == "id"
    assert columns[-3:] == ["created_at", "updated_at", "version"]
    assert table.c.id.primary_key
    assert table.c.id.default is not None
    assert isinstance(table.c.id.default.arg(None), uuid.UUID)
    for name in ("created_at", "updated_at"):
        column_type = table.c[name].type
        assert isinstance(column_type, DateTime)
        assert column_type.timezone
        assert table.c[name].server_default is not None
        assert not table.c[name].nullable
    assert table.c.updated_at.onupdate is not None
    assert _Vessel.__mapper__.version_id_col is table.c.version


def test_naming_convention_gives_deterministic_constraint_names() -> None:
    table = cast(Table, _Vessel.__table__)
    names = {constraint.name for constraint in table.constraints}

    assert "pk_probe_vessels" in names
    assert "uq_probe_vessels_name" in names


def test_every_mapped_relationship_is_lazy_raise() -> None:
    # ADR-0001: nothing may load implicitly in async code.
    offenders = [
        f"{mapper.class_.__name__}.{relationship.key} (lazy={relationship.lazy})"
        for mapper in Base.registry.mappers
        for relationship in mapper.relationships
        if relationship.lazy not in {"raise", "raise_on_sql"}
    ]

    assert offenders == []
