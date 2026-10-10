"""``courses``: the institute-wide course catalogue (Phase 02-1; blueprint §18).

Tenant-scoped (:class:`TenantScopedMixin`) with the realm-agnostic tenant
Row-Level Security policy of migration ``0009``. **No campus column**: a
course belongs to the institute (ADR-0020 §1).

* ``code``: campus-code format, unique per tenant, immutable after creation.
* ``UNIQUE (tenant_id, id)``: target of composite foreign keys (leads, and
  applications in 02-2).
* No hard delete: the runtime role has no DELETE privilege; courses are
  archived.
"""

from sqlalchemy import CheckConstraint, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin, VersionedMixin
from app.core.tenancy import TenantScopedMixin
from app.modules.courses.domain import (
    CODE_MAX_LENGTH,
    CODE_PATTERN,
    DURATION_MAX,
    TEXT_MAX_LENGTH,
    CourseCategory,
    CourseStatus,
    DurationUnit,
)


def _in(column: str, values: type[CourseCategory | CourseStatus | DurationUnit]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


class Course(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "code"),
        CheckConstraint(f"code ~ '{CODE_PATTERN}'", name="code_format"),
        CheckConstraint(_in("category", CourseCategory), name="category"),
        CheckConstraint(_in("status", CourseStatus), name="status"),
        CheckConstraint(_in("duration_unit", DurationUnit), name="duration_unit"),
        CheckConstraint(
            f"duration_value > 0 AND duration_value <= {DURATION_MAX}", name="duration_value"
        ),
        CheckConstraint("(duration_value IS NULL) = (duration_unit IS NULL)", name="duration_pair"),
        CheckConstraint(f"char_length(description) <= {TEXT_MAX_LENGTH}", name="description"),
        CheckConstraint(
            f"char_length(eligibility_summary) <= {TEXT_MAX_LENGTH}", name="eligibility_summary"
        ),
        Index(None, "tenant_id", "status", "name"),
    )

    code: Mapped[str] = mapped_column(String(CODE_MAX_LENGTH), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'DRAFT'"))
    description: Mapped[str | None] = mapped_column(Text)
    eligibility_summary: Mapped[str | None] = mapped_column(Text)
    duration_value: Mapped[int | None] = mapped_column(Integer)
    duration_unit: Mapped[str | None] = mapped_column(String(8))
