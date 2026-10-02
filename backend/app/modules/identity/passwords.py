"""Password hashing (Argon2id) and the common-password blocklist (ADR-0010, D06/D07).

* Argon2id through ``argon2-cffi`` with configurable cost parameters.
  :meth:`PasswordHasher.needs_rehash` reports hashes made with older
  parameters so sign-in can upgrade them.
* A dummy hash is verified for unknown accounts so their timing matches real
  ones (no account enumeration by timing).
* Hashing and verification are CPU-bound and run in a worker thread, never
  inside a database transaction (D02).
* The blocklist is ``data/common-passwords.txt`` (SecLists 10k list, MIT;
  provenance in ``data/common-passwords.LICENSE``), compared case-insensitively.

Nothing here logs: not the password, the hash, the salt or the outcome.
"""

from functools import lru_cache
from pathlib import Path
from typing import Final

import anyio
from argon2 import PasswordHasher as Argon2Hasher
from argon2 import Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

BLOCKLIST_PATH: Final = Path(__file__).parent / "data" / "common-passwords.txt"


@lru_cache(maxsize=1)
def common_passwords() -> frozenset[str]:
    lines = BLOCKLIST_PATH.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip().casefold() for line in lines if line.strip())


class PasswordHasher:
    def __init__(self, *, time_cost: int, memory_cost_kib: int, parallelism: int) -> None:
        self._hasher = Argon2Hasher(
            time_cost=time_cost,
            memory_cost=memory_cost_kib,
            parallelism=parallelism,
            type=Type.ID,
        )
        # Same parameters as real hashes, so verifying it costs the same.
        self._dummy_hash = self._hasher.hash("mti360-dummy-password-for-timing")

    def hash_sync(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify_sync(self, password_hash: str | None, password: str) -> bool:
        """``True`` only for a matching real hash; ``None`` verifies the dummy hash."""
        try:
            self._hasher.verify(password_hash or self._dummy_hash, password)
        except VerifyMismatchError, VerificationError, InvalidHashError:
            return False
        return password_hash is not None

    def needs_rehash(self, password_hash: str) -> bool:
        return self._hasher.check_needs_rehash(password_hash)

    async def hash(self, password: str) -> str:
        return await anyio.to_thread.run_sync(self.hash_sync, password)

    async def verify(self, password_hash: str | None, password: str) -> bool:
        return await anyio.to_thread.run_sync(self.verify_sync, password_hash, password)
