"""Transaction-scoped PostgreSQL settings for Row-Level Security (T01-01; ADR-0004).

Every API and worker transaction publishes its trusted context to PostgreSQL
with ``set_config(name, value, is_local => true)`` — the function form of
``SET LOCAL``. The values disappear when the transaction ends, so nothing can
leak to the next user of a pooled connection.

RLS policies (T01-03 onwards) read them with
``nullif(current_setting('app.tenant_id', true), '')``: once a placeholder
setting has been used in a connection, PostgreSQL reports it as an empty
string (not NULL) outside the transaction that set it.

Values always come from the server-side request context, never from request
input.
"""

import uuid
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

REALM: Final = "app.realm"
REQUEST_ID: Final = "app.request_id"
TENANT_ID: Final = "app.tenant_id"
USER_ID: Final = "app.user_id"

_SET_LOCAL = text("SELECT set_config(:name, :value, true)")


async def apply_transaction_settings(
    session: AsyncSession,
    *,
    realm: str,
    request_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    """Publish the context to the current transaction (``SET LOCAL``).

    Must be called inside an open transaction. ``None`` values are not set, so
    policies see an empty setting and match no tenant rows.
    """
    values = {
        REALM: realm,
        REQUEST_ID: request_id,
        TENANT_ID: tenant_id,
        USER_ID: user_id,
    }
    for name, value in values.items():
        if value is not None:
            await session.execute(_SET_LOCAL, {"name": name, "value": str(value)})
