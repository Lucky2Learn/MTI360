"""Application-level encryption of recoverable secrets (T01-06; ADR-0012).

Used for what cannot be hashed — TOTP shared secrets today:

* **AES-256-GCM** (``cryptography``), a fresh 96-bit nonce per encryption.
* Ciphertext format ``v1:<key-id>:<nonce>:<ciphertext+tag>`` (URL-safe base64,
  no padding).
* **Associated data** binds a ciphertext to its row (for example
  ``platform_mfa_factors:<id>``): moved to another row, it fails to decrypt.
* **Key ring:** ``DATA_ENCRYPTION_KEY`` (32 random bytes, base64) under
  ``DATA_ENCRYPTION_KEY_ID`` encrypts; ``DATA_ENCRYPTION_RETIRED_KEYS``
  (``id:base64`` pairs) only decrypt, until data is re-encrypted.

Plaintext never leaves the credential services. Nothing here logs, and error
messages never contain keys, plaintext or ciphertext.
"""

import base64
import binascii
import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_BYTES: Final = 32
NONCE_BYTES: Final = 12
VERSION: Final = "v1"
KEY_ID_PATTERN: Final = r"^[A-Za-z0-9_-]{1,32}$"
_KEY_ID = re.compile(KEY_ID_PATTERN)
DEVELOPMENT_KEY_ID: Final = "dev"


class EncryptionKeyError(ValueError):
    """An unusable key or key configuration (message never contains the key)."""


class DecryptionError(Exception):
    """A ciphertext that cannot be decrypted with the key ring (tampered, moved or unknown key)."""


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def decode_key(encoded: str) -> bytes:
    """A configured key: standard or URL-safe base64 of exactly 32 bytes."""
    try:
        raw = base64.b64decode(encoded.strip().replace("-", "+").replace("_", "/") + "==")
    except binascii.Error, ValueError:
        raise EncryptionKeyError("not base64") from None
    if len(raw) != KEY_BYTES:
        raise EncryptionKeyError(f"must decode to {KEY_BYTES} bytes")
    return raw


def development_key() -> bytes:
    """A fixed, public key for local development only (never accepted elsewhere)."""
    return hashlib.sha256(b"mti360-development-only-data-encryption-key").digest()


@dataclass(frozen=True, slots=True)
class KeyRing:
    current_id: str
    keys: dict[str, bytes] = field(repr=False)

    def __post_init__(self) -> None:
        if self.current_id not in self.keys:
            raise EncryptionKeyError("the current key is not in the key ring")
        for key_id, key in self.keys.items():
            if not _KEY_ID.fullmatch(key_id):
                raise EncryptionKeyError("invalid key id")
            if len(key) != KEY_BYTES:
                raise EncryptionKeyError(f"keys must be {KEY_BYTES} bytes")

    def encrypt(self, plaintext: bytes, *, associated_data: str) -> str:
        nonce = os.urandom(NONCE_BYTES)
        sealed = AESGCM(self.keys[self.current_id]).encrypt(
            nonce, plaintext, associated_data.encode()
        )
        return ":".join((VERSION, self.current_id, _b64encode(nonce), _b64encode(sealed)))

    def decrypt(self, ciphertext: str, *, associated_data: str) -> bytes:
        parts = ciphertext.split(":")
        if len(parts) != 4 or parts[0] != VERSION or parts[1] not in self.keys:
            raise DecryptionError("unsupported ciphertext")
        try:
            nonce, sealed = _b64decode(parts[2]), _b64decode(parts[3])
            return AESGCM(self.keys[parts[1]]).decrypt(nonce, sealed, associated_data.encode())
        except InvalidTag, binascii.Error, ValueError:
            raise DecryptionError("ciphertext rejected") from None


def parse_retired_keys(value: str) -> dict[str, bytes]:
    """``id:base64,id:base64`` (empty = none)."""
    keys: dict[str, bytes] = {}
    for item in filter(None, (part.strip() for part in value.split(","))):
        key_id, separator, encoded = item.partition(":")
        if not separator or not _KEY_ID.fullmatch(key_id):
            raise EncryptionKeyError("retired keys must be id:base64 pairs")
        keys[key_id] = decode_key(encoded)
    return keys
