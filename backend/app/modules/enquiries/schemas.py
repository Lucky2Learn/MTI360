"""Public enquiry API schemas (Phase 02-4, ADR-0024).

The request never names an institute: the tenant comes from the verified host.
``RequestModel`` rejects unknown fields, so a ``tenant_id`` (or any other
undeclared field) in the body is a 422.
"""

import uuid
from typing import Annotated

from pydantic import Field, StringConstraints

from app.core.schemas import RequestModel, ResponseModel
from app.modules.enquiries.domain import MESSAGE_MAX_LENGTH
from app.modules.leads.domain import EMAIL_MAX_LENGTH, MOBILE_MAX_LENGTH, NAME_MAX_LENGTH


class EnquiryCourse(ResponseModel):
    id: uuid.UUID
    name: str
    category: str


class EnquiryConsent(ResponseModel):
    version: str
    text: str
    retention_months: int


class EnquiryFormOut(ResponseModel):
    """What the hosted page needs: who the institute is, its open courses, the consent."""

    institute_name: str
    courses: list[EnquiryCourse]
    consent: EnquiryConsent
    privacy_notice: str


class EnquiryRequest(RequestModel):
    full_name: Annotated[str, StringConstraints(min_length=1, max_length=NAME_MAX_LENGTH)]
    email: Annotated[str, StringConstraints(max_length=EMAIL_MAX_LENGTH)] | None = None
    mobile: Annotated[str, StringConstraints(max_length=MOBILE_MAX_LENGTH)] | None = None
    course_id: uuid.UUID | None = None
    message: Annotated[str, StringConstraints(max_length=MESSAGE_MAX_LENGTH)] | None = None
    consent_accepted: bool
    consent_version: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    website: Annotated[str, StringConstraints(max_length=200)] = Field(
        default="", description="Leave empty. A filled-in value is treated as automated."
    )


class EnquiryReceived(ResponseModel):
    """The same answer for every accepted submission (new, repeated or discarded)."""

    status: str = "received"
