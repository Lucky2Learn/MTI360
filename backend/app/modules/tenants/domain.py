"""Tenant lifecycle rules (T01-03; PRD.md §13, PLATFORM-ADMIN.md §5-§6, D15, ADR-0014).

Pure rules: no I/O, no framework or database imports.

* All eight lifecycle states are defined. A new tenant starts in ``TRIAL``.
* T01 implements only suspension and reactivation (decision D15). The other
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
