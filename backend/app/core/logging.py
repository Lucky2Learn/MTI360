"""Structured JSON logging with redaction (T01-01; ARCHITECTURE.md §47, CLAUDE.md §67).

One JSON object per line on stdout::

    {"timestamp": "…Z", "level": "INFO", "logger": "app.request", "message": "request.completed",
     "request_id": "…", "realm": "tenant", "method": "GET", "path": "/api/v1/…", "status": 200,
     "duration_ms": 12.3}

* ``request_id`` (the correlation ID), ``realm`` and ``tenant_id`` are added from
  the request context automatically.
* Values of extra fields whose NAME looks sensitive (password, token, secret,
  cookie, authorization, CSRF, session other than ``*session_id``, API key,
  credential, OTP) are replaced by ``[REDACTED]``, and long values are
  truncated. Never put secrets or personal data into the message text itself:
  redaction works on field names.
* Query strings are never logged (they can carry tokens); request logs contain
  the path only. Uvicorn's access log is disabled in favour of the request log,
  and the HTTP client libraries log at WARNING only.
"""

import json
import logging
import re
import sys
import traceback
from datetime import UTC, datetime
from typing import Any, Final

from app.core.context import current_request_id, optional_context

REDACTED: Final = "[REDACTED]"
MAX_VALUE_LENGTH: Final = 1000

SENSITIVE_NAME = re.compile(
    # recovery / totp: MFA material (T01-06).
    r"pass|secret|token|cookie|authori[sz]|csrf|session(?!_id)|api[_-]?key|credential|otp|mfa_code"
    r"|recovery_code|totp",
    re.IGNORECASE,
)

_HANDLER_NAME: Final = "mti360-json"
_STANDARD_ATTRIBUTES: Final = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()
    | {"message", "asctime", "taskName"}
)


def redact(name: str, value: Any) -> Any:
    """Redact by field name; truncate long values; keep JSON-compatible types."""
    if SENSITIVE_NAME.search(name):
        return REDACTED
    if isinstance(value, bool | int | float) or value is None:
        return value
    text = str(value)
    return text if len(text) <= MAX_VALUE_LENGTH else text[:MAX_VALUE_LENGTH] + "…"


class JsonFormatter(logging.Formatter):
    """Formats records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = current_request_id()
        if request_id is not None:
            entry["request_id"] = str(request_id)
        context = optional_context()
        if context is not None:
            entry["realm"] = context.realm.value
            if context.tenant_id is not None:
                entry["tenant_id"] = str(context.tenant_id)
        for name, value in record.__dict__.items():
            if name not in _STANDARD_ATTRIBUTES and not name.startswith("_"):
                entry[name] = redact(name, value)
        if record.exc_info and record.exc_info[1] is not None:
            exc_type, exc, tb = record.exc_info
            entry["exception"] = {
                "type": exc_type.__name__ if exc_type else type(exc).__name__,
                "stack": "".join(traceback.format_exception(exc_type, exc, tb)),
            }
        return json.dumps(entry, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    """Install the JSON handler on the root logger (idempotent).

    Uvicorn's loggers propagate to it; its access log is disabled because the
    request middleware logs every request without the query string.
    """
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if h.get_name() != _HANDLER_NAME]
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    # HTTP client libraries log full URLs (including query strings, which can
    # carry tokens) at INFO; outbound calls are logged by their adapters.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
