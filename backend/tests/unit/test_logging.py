"""Structured logging and redaction (T01-01)."""

import json
import logging
import uuid

import pytest

from app.core.context import bind_request_id, reset_request_id
from app.core.logging import REDACTED, JsonFormatter, configure_logging, redact


def _record(message: str = "event", **extra: object) -> logging.LogRecord:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, message, None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


@pytest.mark.parametrize(
    "name",
    [
        "password",
        "new_password",
        "session_token",
        "reset_token",
        "client_secret",
        "cookie",
        "Authorization",
        "csrf",
        "session",
        "api_key",
        "credentials",
        "otp",
    ],
)
def test_sensitive_field_names_are_redacted(name: str) -> None:
    assert redact(name, "s3cr3t-value") == REDACTED


@pytest.mark.parametrize("name", ["path", "status", "tenant_id", "support_session_id"])
def test_ordinary_field_names_are_kept(name: str) -> None:
    assert redact(name, "value") == "value"


def test_long_values_are_truncated() -> None:
    value = redact("detail", "x" * 5000)

    assert isinstance(value, str)
    assert len(value) == 1001


def test_formatter_emits_single_line_json_with_request_id_and_redaction() -> None:
    request_id = uuid.uuid7()
    token = bind_request_id(request_id)
    try:
        line = JsonFormatter().format(_record("user.signed_in", password="p", path="/api/v1/x"))
    finally:
        reset_request_id(token)

    assert "\n" not in line
    entry = json.loads(line)
    assert entry["message"] == "user.signed_in"
    assert entry["level"] == "INFO"
    assert entry["request_id"] == str(request_id)
    assert entry["password"] == REDACTED
    assert entry["path"] == "/api/v1/x"
    assert entry["timestamp"].endswith("Z")


def test_formatter_includes_exception_type_and_stack() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            "app.test", logging.ERROR, __file__, 1, "failed", None, __import__("sys").exc_info()
        )

    entry = json.loads(JsonFormatter().format(record))

    assert entry["exception"]["type"] == "ValueError"
    assert "boom" in entry["exception"]["stack"]


def test_configure_logging_is_idempotent_and_silences_url_logging() -> None:
    configure_logging("INFO")
    configure_logging("INFO")

    root = logging.getLogger()
    assert [h.get_name() for h in root.handlers].count("mti360-json") == 1
    assert logging.getLogger("uvicorn.access").disabled
    assert logging.getLogger("httpx").level == logging.WARNING
