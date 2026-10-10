"""Per-tenant, per-year number sequences (Phase 02-2; ADR-0021 §7).

One ``INSERT … ON CONFLICT DO UPDATE … RETURNING`` in the caller's
transaction: the row lock serialises concurrent callers of one tenant and
sequence, and a rolled-back transaction rolls the increment back (no gaps).
The year is the database clock's, in UTC. The tenant comes from the trusted
context only.
"""

from typing import Any, cast

from sqlalchemy import Table, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import current_context
from app.core.ids import new_id
from app.modules.students.domain import SequenceName, format_number
from app.modules.students.models import TenantSequence

SEQUENCES = cast(Table, TenantSequence.__table__)


async def next_number(db: AsyncSession, name: SequenceName) -> str:
    tenant_id = current_context().tenant_id
    if tenant_id is None:
        raise RuntimeError("numbers are issued only with a trusted tenant")
    clock: Any = await db.scalar(select(func.date_part("year", func.timezone("UTC", func.now()))))
    year = int(clock)
    statement = (
        insert(SEQUENCES)
        .values(id=new_id(), tenant_id=tenant_id, name=name.value, period=year, last_value=1)
        .on_conflict_do_update(
            index_elements=["tenant_id", "name", "period"],
            set_={"last_value": SEQUENCES.c.last_value + 1, "updated_at": func.now()},
        )
        .returning(SEQUENCES.c.last_value)
    )
    value = int((await db.execute(statement)).scalar_one())
    return format_number(name, year, value)
