"""Tenant lifecycle rules and status access policy (T01-03; D15, ADR-0014)."""

import pytest

from app.modules.tenants.domain import (
    InvalidTenantTransitionError,
    TenantStatus,
    TenantTransition,
    public_access_allowed,
    tenant_access_allowed,
    transition,
)

ALLOWED = {
    (TenantStatus.TRIAL, TenantTransition.SUSPEND): TenantStatus.SUSPENDED,
    (TenantStatus.ACTIVE, TenantTransition.SUSPEND): TenantStatus.SUSPENDED,
    (TenantStatus.PAST_DUE, TenantTransition.SUSPEND): TenantStatus.SUSPENDED,
    (TenantStatus.SUSPENDED, TenantTransition.REACTIVATE): TenantStatus.ACTIVE,
}
EVERY_CASE = [(status, action) for status in TenantStatus for action in TenantTransition]


@pytest.mark.parametrize(("status", "action"), EVERY_CASE)
def test_only_the_t01_transitions_are_allowed(
    status: TenantStatus, action: TenantTransition
) -> None:
    expected = ALLOWED.get((status, action))

    if expected is not None:
        assert transition(status, action) is expected
    else:
        with pytest.raises(InvalidTenantTransitionError) as raised:
            transition(status, action)
        assert raised.value.status is status
        assert raised.value.transition is action


def test_every_status_and_transition_is_covered() -> None:
    assert len(EVERY_CASE) == 8 * 2
    assert len(ALLOWED) == 4


@pytest.mark.parametrize("status", list(TenantStatus))
def test_tenant_and_student_access_is_allowed_in_trial_active_and_past_due(
    status: TenantStatus,
) -> None:
    allowed = status in {TenantStatus.TRIAL, TenantStatus.ACTIVE, TenantStatus.PAST_DUE}

    assert tenant_access_allowed(status) is allowed


@pytest.mark.parametrize("status", list(TenantStatus))
def test_the_public_website_is_served_only_in_trial_and_active(status: TenantStatus) -> None:
    allowed = status in {TenantStatus.TRIAL, TenantStatus.ACTIVE}

    assert public_access_allowed(status) is allowed
