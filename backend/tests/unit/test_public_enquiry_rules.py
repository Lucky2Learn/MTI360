"""Public enquiry pure rules (Phase 02-4, ADR-0024): hosts, slugs, trust, consent, retries."""

from datetime import timedelta

import pytest
from starlette.requests import Request

from app.core.errors import ValidationFailedError
from app.core.net import request_host
from app.core.outbox import error_name, retry_delay
from app.modules.enquiries.domain import CONSENT_VERSION, consent_text, privacy_notice
from app.modules.enquiries.schemas import EnquiryRequest
from app.modules.enquiries.service import _clean, _same_origin
from app.modules.tenants.sites import (
    InvalidSlugError,
    clean_slug,
    normalize_host,
    site_hostname,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("konkan.mti360.in", "konkan.mti360.in"),
        ("KONKAN.MTI360.IN", "konkan.mti360.in"),
        ("konkan.mti360.in:443", "konkan.mti360.in"),
        ("konkan.mti360.in.", "konkan.mti360.in"),
        ("konkan.localhost:3100", "konkan.localhost"),
        ("localhost", None),
        ("127.0.0.1", None),
        ("127.0.0.1:8100", None),
        ("[::1]", None),
        ("user@konkan.mti360.in", None),
        ("konkan.mti360.in/enquiry", None),
        ("konkan.mti360.in:80:80", None),
        ("-konkan.mti360.in", None),
        ("", None),
        (None, None),
    ],
)
def test_hosts_are_normalized_or_rejected(raw: str | None, expected: str | None) -> None:
    assert normalize_host(raw) == expected


@pytest.mark.parametrize("raw", ["konkan", " Konkan ", "konkan-2", "abc"])
def test_valid_slugs(raw: str) -> None:
    assert site_hostname(clean_slug(raw), "mti360.in") == f"{raw.strip().lower()}.mti360.in"


@pytest.mark.parametrize("raw", ["ab", "a" * 41, "app", "www", "-a1", "a1-", "a--b", "a_b", "a.b"])
def test_invalid_slugs(raw: str) -> None:
    with pytest.raises(InvalidSlugError):
        clean_slug(raw)


def _request(headers: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        }
    )


def test_the_host_header_is_used_without_a_trusted_proxy() -> None:
    request = _request({"host": "a.mti360.in", "x-forwarded-host": "b.mti360.in"})
    assert request_host(request, 0) == "a.mti360.in"


def test_only_the_right_most_forwarded_host_counts_behind_a_proxy() -> None:
    request = _request({"host": "api.internal", "x-forwarded-host": "evil.in, b.mti360.in"})
    assert request_host(request, 1) == "b.mti360.in"
    assert request_host(_request({"host": "a.mti360.in"}), 1) is None


@pytest.mark.parametrize(
    ("origin", "host", "same"),
    [
        (None, "a.mti360.in", True),
        ("https://a.mti360.in", "a.mti360.in", True),
        ("https://A.mti360.in:443", "a.mti360.in:443", True),
        ("https://b.mti360.in", "a.mti360.in", False),
        ("null", "a.mti360.in", False),
        ("https://a.mti360.in.evil.example", "a.mti360.in", False),
    ],
)
def test_origin_check(origin: str | None, host: str, same: bool) -> None:
    assert _same_origin(origin, host) is same


def _body(**fields: object) -> EnquiryRequest:
    values: dict[str, object] = {
        "full_name": "Ananya Iyer",
        "email": "ananya@example.com",
        "consent_accepted": True,
        "consent_version": CONSENT_VERSION,
        **fields,
    }
    return EnquiryRequest.model_validate(values)


def test_a_valid_enquiry_is_cleaned() -> None:
    contact = _clean(_body(mobile=" +91  90000 10101 ", message="  When is the next batch?  "))
    assert contact.email_normalized == "ananya@example.com"
    assert contact.mobile == "+91 90000 10101"
    assert contact.mobile_key == "9000010101"
    assert contact.message == "When is the next batch?"


def test_every_problem_is_reported_without_values() -> None:
    with pytest.raises(ValidationFailedError) as raised:
        _clean(_body(email="secret-address", mobile="call me", consent_accepted=False))
    details = {d.field: d.code for d in raised.value.details}
    assert details == {
        "consent_accepted": "consent_required",
        "email": "invalid",
        "mobile": "invalid",
    }
    assert "secret-address" not in str(raised.value.details)


def test_the_consent_and_notice_state_the_retention_period() -> None:
    assert "18 months" in consent_text("Konkan Maritime Training Institute", 18)
    assert "Konkan Maritime Training Institute" in consent_text(
        "Konkan Maritime Training Institute", 12
    )
    assert "18 months" in privacy_notice("Konkan Maritime Training Institute", 18)


def test_unknown_fields_such_as_a_tenant_are_refused() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        _body(tenant_id="01a12bc0-f03f-77b6-9845-868ca4704e8b")


def test_the_retry_schedule_doubles_up_to_an_hour() -> None:
    assert [retry_delay(n) for n in (1, 2, 3, 7, 50)] == [
        timedelta(minutes=1),
        timedelta(minutes=2),
        timedelta(minutes=4),
        timedelta(hours=1),
        timedelta(hours=1),
    ]


def test_only_the_error_class_is_recorded() -> None:
    assert error_name(RuntimeError("smtp said: ananya@example.com rejected")) == "RuntimeError"
