"""Encryption at rest, TOTP and recovery codes (T01-06; ADR-0012, D6-4)."""

import base64
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import SecretStr

from app.core.config import ConfigurationError, load_settings
from app.core.security import totp
from app.core.security.encryption import (
    DEVELOPMENT_KEY_ID,
    DecryptionError,
    EncryptionKeyError,
    KeyRing,
    decode_key,
    parse_retired_keys,
)

KEY = os.urandom(32)
OTHER = os.urandom(32)
TEST_SECRETS = {
    "session_secret": SecretStr("mti360-test-session-secret-0123456789abcdef"),
    "csrf_secret": SecretStr("mti360-test-csrf-secret-0123456789abcdef"),
}


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


# --- AES-256-GCM key ring ---------------------------------------------------------------------


def test_round_trip_and_format() -> None:
    ring = KeyRing("k1", {"k1": KEY})
    sealed = ring.encrypt(b"JBSWY3DPEHPK3PXP", associated_data="platform_mfa_factors:1")
    version, key_id, _nonce, _body = sealed.split(":")
    assert (version, key_id) == ("v1", "k1")
    assert "JBSWY3DPEHPK3PXP" not in sealed
    assert ring.decrypt(sealed, associated_data="platform_mfa_factors:1") == b"JBSWY3DPEHPK3PXP"
    # A fresh nonce every time: the same plaintext never gives the same ciphertext.
    assert sealed != ring.encrypt(b"JBSWY3DPEHPK3PXP", associated_data="platform_mfa_factors:1")


def test_a_ciphertext_is_bound_to_its_row_and_key() -> None:
    ring = KeyRing("k1", {"k1": KEY})
    sealed = ring.encrypt(b"secret", associated_data="user_mfa_factors:a")
    with pytest.raises(DecryptionError):
        ring.decrypt(sealed, associated_data="user_mfa_factors:b")
    with pytest.raises(DecryptionError):
        KeyRing("k1", {"k1": OTHER}).decrypt(sealed, associated_data="user_mfa_factors:a")
    tampered = sealed[:-2] + ("A" if sealed[-2] != "A" else "B") + sealed[-1]
    for bad in (tampered, "v2" + sealed[2:], "v1:k9" + sealed[5:], "garbage"):
        with pytest.raises(DecryptionError):
            ring.decrypt(bad, associated_data="user_mfa_factors:a")


def test_retired_keys_decrypt_but_never_encrypt() -> None:
    old = KeyRing("k1", {"k1": KEY}).encrypt(b"secret", associated_data="row")
    rotated = KeyRing("k2", {"k2": OTHER, "k1": KEY})
    assert rotated.decrypt(old, associated_data="row") == b"secret"
    assert rotated.encrypt(b"secret", associated_data="row").startswith("v1:k2:")


def test_key_parsing_rejects_bad_material_without_echoing_it() -> None:
    assert decode_key(_b64(KEY)) == KEY
    assert decode_key(base64.urlsafe_b64encode(KEY).decode()) == KEY
    for bad in ("not base64!", _b64(os.urandom(16)), ""):
        with pytest.raises(EncryptionKeyError) as caught:
            decode_key(bad)
        assert bad not in str(caught.value) or not bad
    assert parse_retired_keys("") == {}
    assert parse_retired_keys(f"old:{_b64(KEY)}") == {"old": KEY}
    with pytest.raises(EncryptionKeyError):
        parse_retired_keys(_b64(KEY))
    with pytest.raises(EncryptionKeyError):
        KeyRing("k1", {"k1": os.urandom(16)})


# --- Settings ----------------------------------------------------------------------------------


def _settings(env: str, **values: Any) -> Any:
    return load_settings(_env_file=None, app_env=env, **(TEST_SECRETS | values))


def test_the_key_is_required_outside_development() -> None:
    with pytest.raises(ConfigurationError) as caught:
        _settings("test")
    assert "DATA_ENCRYPTION_KEY: must be set in test" in str(caught.value)
    with pytest.raises(ConfigurationError) as invalid:
        _settings("test", data_encryption_key=SecretStr("dGlueQ=="))
    assert "DATA_ENCRYPTION_KEY: must be base64 of 32 random bytes" in str(invalid.value)
    assert "dGlueQ" not in str(invalid.value)


def test_rotation_settings_are_validated() -> None:
    good = SecretStr(_b64(KEY))
    with pytest.raises(ConfigurationError) as caught:
        _settings("test", data_encryption_key=good, data_encryption_retired_keys=SecretStr("x"))
    assert "DATA_ENCRYPTION_RETIRED_KEYS" in str(caught.value)
    with pytest.raises(ConfigurationError) as same_id:
        _settings(
            "test",
            data_encryption_key=good,
            data_encryption_retired_keys=SecretStr(f"k1:{_b64(OTHER)}"),
        )
    assert "must not contain DATA_ENCRYPTION_KEY_ID" in str(same_id.value)
    ring = _settings(
        "test",
        data_encryption_key=good,
        data_encryption_key_id="k2",
        data_encryption_retired_keys=SecretStr(f"k1:{_b64(OTHER)}"),
    ).encryption_keyring()
    assert ring.current_id == "k2"
    assert ring.keys == {"k2": KEY, "k1": OTHER}


def test_development_uses_a_public_development_only_key() -> None:
    ring = load_settings(_env_file=None, app_env="development").encryption_keyring()
    assert ring.current_id == DEVELOPMENT_KEY_ID
    sealed = ring.encrypt(b"x", associated_data="row")
    assert ring.decrypt(sealed, associated_data="row") == b"x"


# --- TOTP (RFC 6238 appendix B, SHA-1) -------------------------------------------------------

RFC_KEY = b"12345678901234567890"
RFC_VECTORS = [
    (59, "94287082"),
    (1111111109, "07081804"),
    (1111111111, "14050471"),
    (1234567890, "89005924"),
    (2000000000, "69279037"),
    (20000000000, "65353130"),
]


@pytest.mark.parametrize(("seconds", "expected"), RFC_VECTORS)
def test_rfc_6238_vectors(seconds: int, expected: str) -> None:
    step = totp.time_step(datetime.fromtimestamp(seconds, UTC))
    assert totp.hotp(RFC_KEY, step, digits=8) == expected
    assert totp.hotp(RFC_KEY, step) == expected[-6:]


def test_codes_match_the_current_step_plus_minus_one() -> None:
    secret = totp.new_secret()
    now = datetime(2026, 10, 2, 12, 0, 15, tzinfo=UTC)
    step = totp.time_step(now)
    for offset in (-1, 0, 1):
        assert totp.matching_step(secret, totp.code_at(secret, step + offset), now) == step + offset
    for offset in (-2, 2):
        assert totp.matching_step(secret, totp.code_at(secret, step + offset), now) is None
    spaced = totp.code_at(secret, step)
    assert totp.matching_step(secret, f"{spaced[:3]} {spaced[3:]}", now) == step
    for bad in ("", "12345", "1234567", "abcdef"):
        assert totp.matching_step(secret, bad, now) is None


def test_secrets_and_provisioning_uri() -> None:
    secret = totp.new_secret()
    assert len(base64.b32decode(secret)) == totp.SECRET_BYTES
    assert secret != totp.new_secret()
    uri = totp.provisioning_uri(secret, "nora@mti360-platform.example")
    assert uri.startswith("otpauth://totp/MTI%20360:nora%40mti360-platform.example?")
    for part in (f"secret={secret}", "issuer=MTI+360", "digits=6", "period=30", "algorithm=SHA1"):
        assert part in uri
    assert totp.time_step(datetime.fromtimestamp(60, UTC) + timedelta(seconds=29)) == 2


# --- Recovery codes ----------------------------------------------------------------------------


def test_recovery_codes() -> None:
    codes = totp.new_recovery_codes()
    assert len(codes) == len(set(codes)) == totp.RECOVERY_CODE_COUNT
    for code in codes:
        assert len(code) == 11
        assert code[5] == "-"
        assert totp.normalize_recovery_code(code) == code.replace("-", "")
        assert totp.normalize_recovery_code(f" {code.upper()} ") == code.replace("-", "")
    for bad in ("", "abc", "abcde-fghi1", "abcde-fghij-k"):
        assert totp.normalize_recovery_code(bad) is None
    first = totp.recovery_code_hash("s", "platform", "u1:abcdefghij")
    assert len(first) == 64
    assert first != totp.recovery_code_hash("s", "tenant", "u1:abcdefghij")
    assert first != totp.recovery_code_hash("s", "platform", "u2:abcdefghij")
