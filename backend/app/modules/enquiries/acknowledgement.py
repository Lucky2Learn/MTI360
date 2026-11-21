"""The acknowledgement email of a public enquiry (outbox kind ``enquiry.acknowledgement``).

Built by the worker at delivery time from the current data, in a system-realm
transaction scoped to the message's tenant (the outbox payload holds only the
lead's ID). A lead that is gone or has no email is a permanent failure: there
is nothing to send, and retrying would not change that. The email contains no
link and nothing the enquirer did not enter.
"""

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.tenancy import system_context
from app.integrations.email import EmailMessage
from app.modules.courses.models import Course
from app.modules.leads.models import Lead
from app.modules.tenants.models import Tenant

TEMPLATE = "enquiry_acknowledgement"


class NothingToSendError(Exception):
    """The message cannot be built (permanent): the lead or its email is gone."""


def acknowledgement_body(*, name: str, institute: str, course: str | None) -> str:
    about = f" about {course}" if course else ""
    return (
        f"Dear {name},\n\n"
        f"Thank you for your enquiry{about}. {institute} has received it, and a counsellor "
        "will contact you soon.\n\n"
        "You do not need to reply to this email. If you did not send this enquiry, you can "
        "ignore it.\n\n"
        f"{institute}\n"
        "Sent through MTI 360"
    )


async def build_acknowledgement(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    payload: Mapping[str, Any],
) -> EmailMessage:
    try:
        lead_id = uuid.UUID(str(payload["lead_id"]))
    except KeyError, ValueError:
        raise NothingToSendError() from None
    async with system_context(factory, tenant_id=tenant_id) as db:
        row = (
            await db.execute(
                select(Lead.full_name, Lead.email, Course.name.label("course"), Tenant.name)
                .join(Tenant, Tenant.id == Lead.tenant_id)
                .outerjoin(
                    Course,
                    and_(
                        Course.tenant_id == Lead.tenant_id,
                        Course.id == Lead.interested_course_id,
                    ),
                )
                .where(Lead.id == lead_id)
            )
        ).one_or_none()
    if row is None or not row.email:
        raise NothingToSendError()
    return EmailMessage(
        to=row.email,
        subject=f"We received your enquiry - {row.name}",
        body=acknowledgement_body(name=row.full_name, institute=row.name, course=row.course),
        template=TEMPLATE,
    )
