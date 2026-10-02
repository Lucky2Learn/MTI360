"""Opaque tokens and their at-rest hashes (ADR-0010 §1, §5; T01-04).

* Tokens are 256 random bits from :mod:`secrets`, URL-safe base64 (43 chars).
* Only ``HMAC-SHA256(SESSION_SECRET, purpose || token)`` is stored, as 64
  lower-case hex characters. The purpose prefix separates the session,
  password-reset and invitation domains, so a hash of one kind can never match
  another kind.
* The CSRF token is ``HMAC-SHA256(CSRF_SECRET, session id)`` (ADR-0010 §5).
* Comparisons are constant-time.

Tokens never appear in logs, URLs paths, query strings, audit metadata or
exception messages.
"""

import hashlib
import hmac
import re
import secrets
import uuid
from enum import StrEnum
from typing import Final

TOKEN_BYTES: Final = 32
TOKEN_PATTERN: Final = r"^[A-Za-z0-9_-]{43}$"  # noqa: S105 - a format, not a secret
TOKEN_HASH_PATTERN: Final = r"^[0-9a-f]{64}$"  # noqa: S105 - a format, not a secret
_TOKEN_RE = re.compile(TOKEN_PATTERN)


class TokenPurpose(StrEnum):
    SESSION = "session"
    PASSWORD_RESET = "password_reset"  # noqa: S105 - a purpose label, not a secret
    INVITATION = "invitation"


def new_token() -> str:
    """A new 256-bit opaque token."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def is_well_formed(token: str) -> bool:
    return _TOKEN_RE.fullmatch(token) is not None


def token_hash(secret: str, purpose: TokenPurpose, token: str) -> str:
    """The stored form of ``token``: keyed, purpose-separated, hex."""
    message = f"{purpose.value}:{token}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def csrf_token(secret: str, session_id: uuid.UUID) -> str:
    return hmac.new(secret.encode(), f"csrf:{session_id}".encode(), hashlib.sha256).hexdigest()


def csrf_valid(secret: str, session_id: uuid.UUID, presented: str | None) -> bool:
    if not presented:
        return False
    return hmac.compare_digest(csrf_token(secret, session_id), presented)
