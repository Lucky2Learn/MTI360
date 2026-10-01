"""Audit metadata: validated, bounded and redacted before persistence (T01-02; ADR-0013 §4).

Metadata is a flat JSON object of code-chosen keys and simple values, never a
request object, header set, body, authentication payload or exception.

* **Keys:** 1 to 64 characters, ``^[a-z][a-z0-9_]*$``, at most
  :data:`MAX_KEYS`.
* **Values:** ``None``, ``bool``, ``int``, finite ``float``, ``str``,
  ``uuid.UUID`` (stored as text), or a list of those with at most
  :data:`MAX_LIST_ITEMS` items. Strings longer than :data:`MAX_STRING_LENGTH`
  are truncated.
* **Sensitive keys are redacted, deterministically:** a key whose name looks
  sensitive (the logging pattern — password, secret, token, cookie,
  authorization, CSRF, session other than ``*session_id``, API key, credential,
  OTP — plus JWT and prompt) keeps its name, and its value is replaced by
  ``[REDACTED]`` before anything is stored. The rule works on key names:
  values under ordinary keys must never contain secrets.
* **Size:** the serialized object is at most :data:`MAX_BYTES` bytes
  (the database enforces a higher ceiling as a backstop).

Anything else raises :class:`AuditMetadataError` — a programming error in the
producer. Error messages never contain metadata values.
"""

import json
import math
import re
import uuid
from collections.abc import Mapping
from typing import Final

from app.core.logging import REDACTED, SENSITIVE_NAME

MAX_KEYS: Final = 32
MAX_KEY_LENGTH: Final = 64
MAX_STRING_LENGTH: Final = 256
MAX_LIST_ITEMS: Final = 16
MAX_BYTES: Final = 4096

KEY_PATTERN: Final = re.compile(r"[a-z][a-z0-9_]*")
SENSITIVE_KEY: Final = re.compile(rf"{SENSITIVE_NAME.pattern}|jwt|prompt", re.IGNORECASE)

type Scalar = str | int | float | bool | None
type MetadataValue = Scalar | list[Scalar]


class AuditMetadataError(ValueError):
    """Metadata that breaks the contract. The message never contains values."""


def _scalar(key: str, value: object) -> Scalar:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AuditMetadataError(f"metadata value of {key!r} is not a finite number")
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, str):
        return value if len(value) <= MAX_STRING_LENGTH else value[:MAX_STRING_LENGTH] + "…"
    raise AuditMetadataError(
        f"metadata value of {key!r} has an unsupported type ({type(value).__name__})"
    )


def safe_metadata(values: Mapping[str, object] | None) -> dict[str, MetadataValue]:
    """Validate, redact and bound audit metadata (see the module documentation)."""
    if not values:
        return {}
    if len(values) > MAX_KEYS:
        raise AuditMetadataError(f"metadata has more than {MAX_KEYS} keys")
    result: dict[str, MetadataValue] = {}
    for key, value in values.items():
        if not isinstance(key, str) or len(key) > MAX_KEY_LENGTH or not KEY_PATTERN.fullmatch(key):
            # The key itself is not echoed: it may not be code-defined.
            raise AuditMetadataError("metadata key is not a lower-case identifier")
        if SENSITIVE_KEY.search(key):
            result[key] = REDACTED
        elif isinstance(value, list | tuple):
            if len(value) > MAX_LIST_ITEMS:
                raise AuditMetadataError(f"metadata list {key!r} has too many items")
            result[key] = [_scalar(key, item) for item in value]
        else:
            result[key] = _scalar(key, value)
    if len(json.dumps(result, ensure_ascii=False).encode()) > MAX_BYTES:
        raise AuditMetadataError(f"metadata exceeds {MAX_BYTES} bytes")
    return result
