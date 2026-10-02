"""TOTP (RFC 6238) and recovery codes (T01-06; D6-4).

* HOTP/TOTP with HMAC-SHA-1, 6 digits, 30-second steps; verification accepts
  the current step ±1 and returns the **step** that matched, so the caller
  can store it and refuse any code from the same or an earlier step (replay).
* Secrets are 160 random bits, base32 without padding (authenticator apps).
* ``otpauth://`` URIs for manual setup (no QR dependency, decision D6-4).
* Recovery codes: 10 single-use codes of 10 base32 characters (50 bits),
  shown as ``xxxxx-xxxxx``; stored only as purpose-separated HMACs.

Comparisons are constant-time. Nothing here logs.
"""

import base64
import hashlib
import hmac
import secrets
import struct
from datetime import datetime
from typing import Final
from urllib.parse import quote, urlencode

DIGITS: Final = 6
STEP_SECONDS: Final = 30
TOLERANCE_STEPS: Final = 1
SECRET_BYTES: Final = 20
ISSUER: Final = "MTI 360"
RECOVERY_CODE_COUNT: Final = 10
_RECOVERY_ALPHABET: Final = "abcdefghijklmnopqrstuvwxyz234567"
_RECOVERY_LENGTH: Final = 10


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode().rstrip("=")


def _key(secret_b32: str) -> bytes:
    return base64.b32decode(secret_b32.upper() + "=" * (-len(secret_b32) % 8))


def hotp(key: bytes, counter: int, digits: int = DIGITS) -> str:
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def time_step(moment: datetime) -> int:
    return int(moment.timestamp()) // STEP_SECONDS


def code_at(secret_b32: str, step: int) -> str:
    return hotp(_key(secret_b32), step)


def matching_step(secret_b32: str, code: str, moment: datetime) -> int | None:
    """The step (current ±1) whose code equals ``code``, newest first; ``None`` otherwise."""
    candidate = code.strip().replace(" ", "")
    if len(candidate) != DIGITS or not candidate.isdigit():
        return None
    key = _key(secret_b32)
    current = time_step(moment)
    found = None
    for step in range(current - TOLERANCE_STEPS, current + TOLERANCE_STEPS + 1):
        if hmac.compare_digest(hotp(key, step), candidate):
            found = step
    return found


def provisioning_uri(secret_b32: str, account: str) -> str:
    query = urlencode(
        {
            "secret": secret_b32,
            "issuer": ISSUER,
            "algorithm": "SHA1",
            "digits": DIGITS,
            "period": STEP_SECONDS,
        }
    )
    return f"otpauth://totp/{quote(ISSUER)}:{quote(account)}?{query}"


def new_recovery_codes() -> list[str]:
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(_RECOVERY_LENGTH))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def normalize_recovery_code(code: str) -> str | None:
    """Lower case without spaces or hyphens; ``None`` when it cannot be a recovery code."""
    raw = code.strip().lower().replace("-", "").replace(" ", "")
    if len(raw) != _RECOVERY_LENGTH or any(c not in _RECOVERY_ALPHABET for c in raw):
        return None
    return raw


def recovery_code_hash(secret: str, purpose: str, normalized_code: str) -> str:
    message = f"{purpose}:{normalized_code}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
