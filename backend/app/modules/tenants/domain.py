"""Tenant lifecycle rules (T01-03; PRD.md §13, PLATFORM-ADMIN.md §5-§6, D15, ADR-0014).

Pure rules: no I/O, no framework or database imports.

* All eight lifecycle states are defined. A new tenant starts in ``TRIAL``.
* T01 implements only suspension (TRIAL, ACTIVE or PAST_DUE → SUSPENDED) and
  reactivation (SUSPENDED → ACTIVE), decision D15. The other
  transitions (provisioning, activation, past due, cancellation,
  deactivation) are defined with the full matrix in T02-05 (INC-32).
"""

from enum import StrEnum


class TenantStatus(StrEnum):
    """The tenant lifecycle states, stored as-is (upper case) in ``tenants.status``."""

    PROSPECT = "PROSPECT"
    TRIAL = "TRIAL"
    PROVISIONING = "PROVISIONING"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"
    DEACTIVATED = "DEACTIVATED"


INITIAL_STATUS = TenantStatus.TRIAL
"""The status of a newly created tenant."""


class TenantTransition(StrEnum):
    """The lifecycle transitions available in T01 (decision D15)."""

    SUSPEND = "suspend"
    REACTIVATE = "reactivate"


_TRANSITIONS: dict[TenantTransition, tuple[frozenset[TenantStatus], TenantStatus]] = {
    TenantTransition.SUSPEND: (
        frozenset({TenantStatus.TRIAL, TenantStatus.ACTIVE, TenantStatus.PAST_DUE}),
        TenantStatus.SUSPENDED,
    ),
    TenantTransition.REACTIVATE: (frozenset({TenantStatus.SUSPENDED}), TenantStatus.ACTIVE),
}


class InvalidTenantTransitionError(ValueError):
    """The transition is not allowed from the tenant's current status."""

    def __init__(self, transition: TenantTransition, status: TenantStatus) -> None:
        super().__init__(f"cannot {transition.value} a tenant in status {status.value}")
        self.transition = transition
        self.status = status


def transition(status: TenantStatus, action: TenantTransition) -> TenantStatus:
    """The status after ``action``; raises :class:`InvalidTenantTransitionError`."""
    sources, target = _TRANSITIONS[action]
    if status not in sources:
        raise InvalidTenantTransitionError(action, status)
    return target


# --- Status access policy (D15; tenancy.md §2) -------------------------------------------

TENANT_ACCESS_STATUSES = frozenset({TenantStatus.TRIAL, TenantStatus.ACTIVE, TenantStatus.PAST_DUE})
"""Statuses in which the tenant application and the student portal are accessible."""

PUBLIC_ACCESS_STATUSES = frozenset({TenantStatus.TRIAL, TenantStatus.ACTIVE})
"""Statuses in which the tenant's public website is served."""


def tenant_access_allowed(status: TenantStatus) -> bool:
    """Whether tenant staff and students may use the tenant (tenant and student realms)."""
    return status in TENANT_ACCESS_STATUSES


def public_access_allowed(status: TenantStatus) -> bool:
    """Whether the tenant's public website is served (public realm)."""
    return status in PUBLIC_ACCESS_STATUSES
