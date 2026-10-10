"""Identity rules, tokens, passwords and client IP without I/O (T01-04)."""

import itertools
import re
import time
import uuid
from datetime import timedelta

import pytest
from starlette.requests import Request

from app.core.net import client_ip
from app.modules.identity import domain
from app.modules.identity.domain import (
    CampusScope,
    CampusState,
    InvalidEmailError,
    MembershipStatus,
    PasswordProblem,
    lockout_duration,
    mask_email,
    membership_usable,
    normalize_email,
    password_problem,
    resolve_campus,
)
from app.modules.identity.passwords import PasswordHasher, common_passwords
from app.modules.identity.tokens import (
    TokenPurpose,
    csrf_token,
    csrf_valid,
    is_well_formed,
    new_token,
    token_hash,
)

SECRET = "mti360-test-session-secret-0123456789abcdef"
A1, A2, A3 = uuid.uuid7(), uuid.uuid7(), uuid.uuid7()

# --- Email ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("  Captain.Rao@WesternMaritime.EDU ", "captain.rao@westernmaritime.edu"),
        ("cadet@konkan.example", "cadet@konkan.example"),
    ],
)
def test_emails_are_trimmed_and_lower_cased(raw: str, canonical: str) -> None:
    assert normalize_email(raw) == canonical


@pytest.mark.parametrize(
    "raw",
    ["", "no-at-sign", "two@@x.example", "a b@x.example", "a@b", "a@.b", "a@b.", "a@.", "@b.c"],
)
def test_implausible_emails_are_rejected(raw: str) -> None:
    with pytest.raises(InvalidEmailError):
        normalize_email(raw)


def test_the_email_rule_is_unchanged_by_the_linear_pattern() -> None:
    """Every string over a small alphabet, up to six characters, is accepted exactly when
    the earlier single pattern accepted it (kept here as the specification only)."""
    earlier = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    for length in range(7):
        for characters in itertools.product("a.@ \t", repeat=length):
            raw = "".join(characters)
            try:
                normalize_email(raw)
                accepted = True
            except InvalidEmailError:
                accepted = False
            assert accepted is bool(earlier.fullmatch(raw.strip().lower())), repr(raw)


def test_the_email_pattern_is_linear_on_hostile_input() -> None:
    """CodeQL py/polynomial-redos: "!@!." followed by many "!." made the earlier pattern
    quadratic (40 000 characters took seconds). The length limit is not relied on here."""
    hostile = "!@!." + "!." * 100_000 + "@"
    started = time.perf_counter()
    assert domain._EMAIL_PATTERN.fullmatch(hostile) is None
    assert time.perf_counter() - started < 0.5  # linear: about a millisecond
    with pytest.raises(InvalidEmailError):
        normalize_email(hostile)


def test_masked_email_keeps_only_the_first_character_and_the_domain() -> None:
    assert mask_email("rao@westernmaritime.edu") == "r•••@westernmaritime.edu"


# --- Passwords -----------------------------------------------------------------------------


def test_password_policy_is_length_and_blocklist_only() -> None:
    blocklist = common_passwords()

    assert password_problem("short pass", blocklist) is PasswordProblem.TOO_SHORT
    assert password_problem("x" * 129, blocklist) is PasswordProblem.TOO_LONG
    assert password_problem("unbelievable", blocklist) is PasswordProblem.COMMON
    assert password_problem("UnBelievable", blocklist) is PasswordProblem.COMMON  # case-insensitive
    # No composition rules: lower-case words with spaces are fine.
    assert password_problem("mooring lines at dawn", blocklist) is None
    assert password_problem("x" * 128, blocklist) is None


def test_the_bundled_blocklist_is_the_10k_list() -> None:
    blocklist = common_passwords()

    # SecLists 10k-most-common.txt (10,001 lines, all distinct), unmodified.
    assert len(blocklist) == 10_001
    assert {"123456", "unbelievable"} <= blocklist


def test_argon2id_hashes_verify_and_report_rehash() -> None:
    hasher = PasswordHasher(time_cost=1, memory_cost_kib=8, parallelism=1)
    stronger = PasswordHasher(time_cost=2, memory_cost_kib=16, parallelism=1)

    password_hash = hasher.hash_sync("Bosun's whistle at 0600 hours")

    assert password_hash.startswith("$argon2id$")
    assert hasher.verify_sync(password_hash, "Bosun's whistle at 0600 hours")
    assert not hasher.verify_sync(password_hash, "bosun's whistle at 0600 hours")
    assert not hasher.verify_sync(None, "anything")  # dummy hash for unknown accounts
    assert not hasher.verify_sync("not-a-hash", "anything")
    assert not hasher.needs_rehash(password_hash)
    assert stronger.needs_rehash(password_hash)


# --- Lockout -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("failures", "minutes"),
    [(0, None), (4, None), (5, 1), (6, 5), (7, 15), (8, 60), (30, 60)],
)
def test_lockout_is_progressive_and_capped(failures: int, minutes: int | None) -> None:
    expected = None if minutes is None else timedelta(minutes=minutes)

    assert lockout_duration(failures) == expected


# --- Campus selection (D04) ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("scope", "permitted", "current", "expected"),
    [
        # Rule 1/4: all-campus scope starts at "All campuses", no step.
        (CampusScope.ALL, [A1, A2], None, CampusState(True, None, True, False)),
        (CampusScope.ALL, [A1, A2], A2, CampusState(True, A2, True, False)),
        # Rule 2: exactly one permitted campus is selected automatically.
        (CampusScope.ALL, [A1], None, CampusState(True, A1, False, False)),
        (CampusScope.SELECTED, [A1], None, CampusState(True, A1, False, False)),
        # Rule 3/5: restricted with two or more must choose, never "all".
        (CampusScope.SELECTED, [A1, A2], None, CampusState(True, None, False, True)),
        (CampusScope.SELECTED, [A1, A2], A1, CampusState(True, A1, False, False)),
        # Rule 8: a withdrawn campus is dropped and the rules re-applied.
        (CampusScope.SELECTED, [A1, A2], A3, CampusState(True, None, False, True)),
        (CampusScope.ALL, [A1, A2], A3, CampusState(True, None, True, False)),
        # Rule 5: restricted with no campus cannot be used.
        (CampusScope.SELECTED, [], None, CampusState(False, None, False, False)),
        # All-campus scope in an institute without campuses is still usable.
        (CampusScope.ALL, [], None, CampusState(True, None, False, False)),
    ],
)
def test_campus_resolution(
    scope: CampusScope, permitted: list[uuid.UUID], current: uuid.UUID | None, expected: CampusState
) -> None:
    assert resolve_campus(scope, permitted, current) == expected


def test_membership_usability_needs_active_status_accessible_tenant_and_campus() -> None:
    usable = CampusState(True, None, True, False)
    unusable = CampusState(False, None, False, False)

    assert membership_usable(MembershipStatus.ACTIVE, True, usable)
    for status in (MembershipStatus.INVITED, MembershipStatus.SUSPENDED, MembershipStatus.REVOKED):
        assert not membership_usable(status, True, usable)
    assert not membership_usable(MembershipStatus.ACTIVE, False, usable)
    assert not membership_usable(MembershipStatus.ACTIVE, True, unusable)


# --- Tokens --------------------------------------------------------------------------------


def test_tokens_are_256_bit_and_stored_only_as_purpose_bound_hmacs() -> None:
    tokens = {new_token() for _ in range(200)}
    token = next(iter(tokens))

    assert len(tokens) == 200
    assert all(is_well_formed(t) and len(t) == 43 for t in tokens)
    hashes = {token_hash(SECRET, purpose, token) for purpose in TokenPurpose}
    assert len(hashes) == len(TokenPurpose)  # a session hash never matches a reset hash
    assert all(len(h) == 64 and token not in h for h in hashes)
    assert token_hash(SECRET, TokenPurpose.SESSION, token) == token_hash(
        SECRET, TokenPurpose.SESSION, token
    )
    assert (
        token_hash("another-secret-0123456789abcdef0123", TokenPurpose.SESSION, token) not in hashes
    )


@pytest.mark.parametrize("value", ["", "short", "a" * 42, "a" * 44, "a" * 42 + "!", "../" * 15])
def test_malformed_tokens_are_rejected(value: str) -> None:
    assert not is_well_formed(value)


def test_csrf_tokens_are_bound_to_the_session() -> None:
    session_id, other = uuid.uuid7(), uuid.uuid7()
    token = csrf_token(SECRET, session_id)

    assert csrf_valid(SECRET, session_id, token)
    assert not csrf_valid(SECRET, other, token)
    assert not csrf_valid(SECRET, session_id, None)
    assert not csrf_valid(SECRET, session_id, "")
    assert not csrf_valid(SECRET, session_id, token.upper())


# --- Client IP (D08) -----------------------------------------------------------------------


def _request(peer: str, *forwarded: str) -> Request:
    headers = [(b"x-forwarded-for", value.encode()) for value in forwarded]
    return Request({"type": "http", "client": (peer, 1234), "headers": headers})


def test_forwarded_headers_are_ignored_without_trusted_proxies() -> None:
    request = _request("203.0.113.9", "198.51.100.1")

    assert client_ip(request, 0) == "203.0.113.9"


def test_only_entries_added_by_trusted_proxies_are_used() -> None:
    # The client forged "1.2.3.4"; the trusted proxy appended the real address.
    request = _request("10.0.0.2", "1.2.3.4, 198.51.100.7")

    assert client_ip(request, 1) == "198.51.100.7"
    assert client_ip(request, 2) == "1.2.3.4"
    assert client_ip(request, 5) == "1.2.3.4"  # never beyond the leftmost entry


def test_invalid_addresses_become_unknown() -> None:
    assert client_ip(_request("10.0.0.2", "not-an-ip"), 1) == "unknown"
    assert client_ip(_request("testclient"), 0) == "unknown"
