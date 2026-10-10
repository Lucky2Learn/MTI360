"""``tenant_sequences``: one counter per tenant, sequence and period (ADR-0021 §7; ADR-0022 §3).

Created by migration ``0010`` (tenant RLS, no DELETE privilege, nothing for
the read-only role). ``period`` is a calendar year or a financial-year start
year, by sequence (:data:`app.core.sequences.numbering.PERIODS`). The model
lives in ``core`` so that every module can number its documents without
importing another module.
"""

from collections.abc import Iterable

from sqlalchemy import BigInteger, CheckConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin
from app.core.sequences.numbering import SequenceName
from app.core.tenancy import TenantScopedMixin


def _in(column: str, values: Iterable[str]) -> str:
    return f"{column} IN ({', '.join(repr(str(value)) for value in values)})"


class TenantSequence(TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "tenant_sequences"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "name", "period"),
        CheckConstraint(_in("name", [s.value for s in SequenceName]), name="name"),
        CheckConstraint("period BETWEEN 2000 AND 9999", name="period"),
        CheckConstraint("last_value > 0", name="last_value"),
    )

    name: Mapped[str] = mapped_column(String(16), nullable=False)
    period: Mapped[int] = mapped_column(Integer, nullable=False)
    last_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
