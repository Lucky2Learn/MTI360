"""Audit vocabulary: categories, event types and targets (T01-02; ADR-0013).

The category is the broad classification of an audit event; the set is closed
and the database enforces it. The event type identifies the specific event.
Event types are declared in code by the module that produces them, as
module-level constants::

    LOGIN_FAILED = AuditEventType("auth.login_failed", AuditCategory.SECURITY)

The writers accept only :class:`AuditEventType` values, never a free string,
so no request input can choose an event type. Each type belongs to exactly one
category. New event types need no schema change.
"""

import re
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

EVENT_TYPE_MAX_LENGTH: Final = 100
EVENT_TYPE_PATTERN: Final = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$"
"""Dotted lower-case names such as ``auth.login_failed`` (at least two segments)."""

TARGET_TYPE_MAX_LENGTH: Final = 64
TARGET_TYPE_PATTERN: Final = r"^[a-z][a-z0-9_]*$"
"""Lower-case resource names such as ``campus`` or ``tenant_role``."""


class AuditCategory(StrEnum):
    """Approved audit categories (ADR-0013 §2)."""

    SECURITY = "security"
    """Authentication, authorization and abuse signals. Written through the
    security-event buffer, after the request transaction (ADR-0013 §5)."""
    ADMIN = "admin"
    """Administrative changes: tenants, users, roles, configuration."""
    DATA_ACCESS = "data_access"
    """Reads of sensitive data that must be traceable (support access, exports)."""
    DOMAIN = "domain"
    """Business changes recorded with the mutation (finance, compliance, …)."""


@dataclass(frozen=True, slots=True)
class AuditEventType:
    """A specific, code-declared audit event and its category."""

    name: str
    category: AuditCategory

    def __post_init__(self) -> None:
        if len(self.name) > EVENT_TYPE_MAX_LENGTH or not re.fullmatch(
            EVENT_TYPE_PATTERN, self.name
        ):
            raise ValueError(f"invalid audit event type name: {self.name!r}")
        if not isinstance(self.category, AuditCategory):
            raise TypeError("audit event category must be an AuditCategory")


@dataclass(frozen=True, slots=True)
class AuditTarget:
    """The resource an event is about: a resource type and, optionally, its ID.

    Generic on purpose: no foreign key and no relationship, so the audit
    foundation never depends on the modules whose resources it records.
    """

    type: str
    id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        if len(self.type) > TARGET_TYPE_MAX_LENGTH or not re.fullmatch(
            TARGET_TYPE_PATTERN, self.type
        ):
            raise ValueError("invalid audit target type")
        if self.id is not None and not isinstance(self.id, uuid.UUID):
            raise TypeError("audit target id must be a UUID")
