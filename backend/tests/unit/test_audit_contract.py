"""Audit vocabulary, metadata contract and writer guards (T01-02; ADR-0013).

No database: these tests prove what is rejected or redacted BEFORE anything
can be persisted. The database guarantees are in tests/integration.
"""

import json
import uuid
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import (
    AuditCategory,
    AuditEventType,
    AuditMetadataError,
    AuditTarget,
    record_security_event,
    safe_metadata,
    write_audit_event,
)
from app.core.audit.metadata import MAX_BYTES, MAX_KEYS, MAX_LIST_ITEMS, MAX_STRING_LENGTH
from app.core.audit.security import (
    MAX_BUFFERED_EVENTS,
    SecurityEventBuffer,
    _buffer,
)
from app.core.audit.writer import audit_row
from app.core.context import MissingContextError, Realm, RequestContext
from app.core.context import _context as _request_context
from app.core.logging import REDACTED

DOMAIN_EVENT = AuditEventType("probe.updated", AuditCategory.DOMAIN)
SECURITY_EVENT = AuditEventType("auth.probe_failed", AuditCategory.SECURITY)

# Every name the T01-02 specification forbids from persisting.
FORBIDDEN_KEYS = (
    "password",
    "password_hash",
    "access_token",
    "refresh_token",
    "jwt",
    "api_key",
    "secret",
    "otp",
    "mfa_secret",
    "session_token",
    "authorization",
    "cookie",
    "raw_prompt",
    "provider_secret",
)
SECRET_VALUE = "s3cr3t-value-that-must-never-be-stored"


# --- Categories and event types ------------------------------------------------------


def test_categories_are_exactly_the_approved_set() -> None:
    assert {category.value for category in AuditCategory} == {
        "security",
        "admin",
        "data_access",
        "domain",
    }


@pytest.mark.parametrize(
    "name",
    ["auth.login_failed", "tenant.campus.suspended", "a.b", "admin.role_2_granted"],
)
def test_event_types_accept_dotted_lower_case_names(name: str) -> None:
    assert AuditEventType(name, AuditCategory.ADMIN).name == name


@pytest.mark.parametrize(
    "name",
    ["login", "Auth.failed", "auth..failed", "auth.failed.", "1auth.failed", "auth.fail ed", ""],
)
def test_event_types_reject_unstructured_names(name: str) -> None:
    with pytest.raises(ValueError, match="invalid audit event type"):
        AuditEventType(name, AuditCategory.ADMIN)


def test_event_types_are_bounded_and_need_a_real_category() -> None:
    with pytest.raises(ValueError, match="invalid audit event type"):
        AuditEventType("a." + "b" * 99, AuditCategory.ADMIN)
    with pytest.raises(TypeError):
        AuditEventType("auth.failed", cast(AuditCategory, "audit"))


def test_targets_are_generic_type_and_uuid() -> None:
    target_id = uuid.uuid7()

    assert AuditTarget("campus", target_id).id == target_id
    assert AuditTarget("tenant_role").id is None
    for bad_type in ("Campus", "campus-id", "", "x" * 65):
        with pytest.raises(ValueError, match="invalid audit target type"):
            AuditTarget(bad_type)
    with pytest.raises(TypeError):
        AuditTarget("campus", cast(uuid.UUID, str(target_id)))


# --- Metadata ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", FORBIDDEN_KEYS)
def test_sensitive_metadata_keys_are_redacted_before_persistence(key: str) -> None:
    result = safe_metadata({key: SECRET_VALUE, "attempts": 3})

    assert result == {key: REDACTED, "attempts": 3}
    assert SECRET_VALUE not in json.dumps(result)


def test_sensitive_values_inside_lists_are_redacted_by_their_key() -> None:
    assert safe_metadata({"api_keys": [SECRET_VALUE, SECRET_VALUE]}) == {"api_keys": REDACTED}


def test_session_ids_are_not_mistaken_for_session_secrets() -> None:
    session_id = uuid.uuid7()

    assert safe_metadata({"auth_session_id": session_id}) == {"auth_session_id": str(session_id)}


def test_metadata_keeps_simple_typed_values() -> None:
    value = uuid.uuid7()

    assert safe_metadata(
        {"count": 2, "ratio": 0.5, "ok": True, "note": None, "id": value, "codes": ["a", 1]}
    ) == {"count": 2, "ratio": 0.5, "ok": True, "note": None, "id": str(value), "codes": ["a", 1]}
    assert safe_metadata(None) == {}
    assert safe_metadata({}) == {}


def test_long_strings_are_truncated_deterministically() -> None:
    result = safe_metadata({"reason": "x" * (MAX_STRING_LENGTH + 50)})

    assert result["reason"] == "x" * MAX_STRING_LENGTH + "…"
    assert safe_metadata({"reason": "x" * (MAX_STRING_LENGTH + 50)}) == result


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"payload": {"nested": SECRET_VALUE}}, "unsupported type"),
        ({"body": b"raw"}, "unsupported type"),
        ({"error": RuntimeError(SECRET_VALUE)}, "unsupported type"),
        ({"ratio": float("nan")}, "not a finite number"),
        ({"codes": list(range(MAX_LIST_ITEMS + 1))}, "too many items"),
        ({f"k{i}": i for i in range(MAX_KEYS + 1)}, "more than"),
        ({"Header-Value": "x"}, "not a lower-case identifier"),
        ({"k" * 65: "x"}, "not a lower-case identifier"),
        ({f"k{i}": "x" * MAX_STRING_LENGTH for i in range(20)}, f"exceeds {MAX_BYTES} bytes"),
    ],
)
def test_metadata_outside_the_contract_is_rejected_without_echoing_values(
    values: dict[str, Any], message: str
) -> None:
    with pytest.raises(AuditMetadataError, match=message) as error:
        safe_metadata(values)

    assert SECRET_VALUE not in str(error.value)


def test_rejected_metadata_never_echoes_an_unexpected_key() -> None:
    with pytest.raises(AuditMetadataError) as error:
        safe_metadata({f"Bearer {SECRET_VALUE}": 1})

    assert SECRET_VALUE not in str(error.value)


# --- Rows and writers -------------------------------------------------------------------


def _context(**overrides: Any) -> RequestContext:
    values: dict[str, Any] = {"realm": Realm.TENANT, "request_id": uuid.uuid7()}
    return RequestContext(**(values | overrides))


def test_rows_take_realm_tenant_principal_and_request_from_the_trusted_context() -> None:
    context = _context(tenant_id=uuid.uuid7(), principal_id=uuid.uuid7())
    target = AuditTarget("campus", uuid.uuid7())

    row = audit_row(context, DOMAIN_EVENT, target=target, metadata={"password": SECRET_VALUE})

    assert row["id"].version == 7
    assert row["realm"] == "tenant"
    assert (row["tenant_id"], row["principal_id"], row["request_id"]) == (
        context.tenant_id,
        context.principal_id,
        context.request_id,
    )
    assert (row["category"], row["event_type"]) == ("domain", "probe.updated")
    assert (row["target_type"], row["target_id"]) == ("campus", target.id)
    assert row["metadata"] == {"password": REDACTED}


def test_rows_accept_only_declared_event_types() -> None:
    with pytest.raises(TypeError, match="AuditEventType"):
        audit_row(_context(), cast(AuditEventType, "auth.login_failed"))


class _SessionOutsideTransaction:
    def in_transaction(self) -> bool:
        return False


@pytest.mark.anyio
async def test_the_transactional_writer_needs_a_context_and_a_transaction() -> None:
    session = cast(AsyncSession, _SessionOutsideTransaction())
    token = _request_context.set(None)
    try:
        with pytest.raises(MissingContextError):
            await write_audit_event(session, DOMAIN_EVENT)
        _request_context.set(_context())
        with pytest.raises(ValueError, match="record_security_event"):
            await write_audit_event(session, SECURITY_EVENT)
        with pytest.raises(RuntimeError, match="inside the request transaction"):
            await write_audit_event(session, DOMAIN_EVENT)
    finally:
        _request_context.reset(token)


def test_security_events_need_an_open_scope() -> None:
    with pytest.raises(MissingContextError, match="no security-event scope"):
        record_security_event(SECURITY_EVENT)


def test_the_security_writer_accepts_only_security_events_and_bounds_the_buffer() -> None:
    buffer = SecurityEventBuffer(context=_context())
    _buffer.set(buffer)
    try:
        with pytest.raises(ValueError, match="security events only"):
            record_security_event(DOMAIN_EVENT)
        for _ in range(MAX_BUFFERED_EVENTS + 3):
            record_security_event(SECURITY_EVENT, metadata={"token": SECRET_VALUE})
    finally:
        _buffer.set(None)

    assert len(buffer.rows) == MAX_BUFFERED_EVENTS
    assert buffer.dropped == 3
    assert all(row["metadata"] == {"token": REDACTED} for row in buffer.rows)
    assert {row["request_id"] for row in buffer.rows} == {buffer.context.request_id}
