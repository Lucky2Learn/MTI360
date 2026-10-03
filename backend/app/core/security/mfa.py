"""MFA factor and recovery-code storage, shared by both realms (T01-06; D6-4).

:class:`MfaStore` works on a realm's own tables (``platform_mfa_factors`` /
``platform_recovery_codes`` or ``user_mfa_factors`` / ``user_recovery_codes``),
named by the owner column, so the platform and tenant realms never share
rows. Callers run it inside a transaction whose RLS context reaches only the
owner's rows (migration ``0006``).

* **Enrolment** creates an unconfirmed factor with an encrypted secret (the
  plaintext secret is returned once). Confirmation consumes a first code and
  issues recovery codes.
* **Verification** accepts the current TOTP step ±1 and stores the matched
  step with an atomic ``UPDATE … WHERE last_used_step < :step``: a code can
  be used once, and never after a newer one (replay protection).
* **Recovery codes** are single-use: an atomic ``UPDATE … WHERE used_at IS
  NULL`` consumes one. They are stored as HMACs bound to their owner.

A secret that cannot be decrypted (wrong key ring, tampered row) fails
closed: verification returns ``False`` and an event without values is logged.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import Table, func, insert, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_id
from app.core.security import totp
from app.core.security.encryption import DecryptionError, KeyRing

logger = logging.getLogger("app.security.mfa")

TOTP = "totp"


class MfaAlreadyEnabledError(Exception):
    """Enrolment was started while a confirmed factor exists."""


@dataclass(frozen=True, slots=True)
class Enrolment:
    secret: str
    """Base32 TOTP secret: returned once, for manual setup."""
    otpauth_uri: str


@dataclass(frozen=True, slots=True)
class _Factor:
    id: uuid.UUID
    secret_ciphertext: str
    confirmed: bool


def _rowcount(result: object) -> int:
    """Rows matched by an UPDATE (executed through ``AsyncSession.execute``)."""
    return cast(CursorResult[object], result).rowcount


@dataclass(frozen=True, slots=True)
class MfaStore:
    factors: Table
    codes: Table
    owner: str
    """Owner column: ``user_id`` or ``platform_user_id``."""
    code_secret: str
    """HMAC key of recovery codes (the session secret)."""
    code_purpose: str

    def _associated(self, factor_id: uuid.UUID) -> str:
        return f"{self.factors.name}:{factor_id}"

    def code_hash(self, owner_id: uuid.UUID, code: str) -> str | None:
        normalized = totp.normalize_recovery_code(code)
        if normalized is None:
            return None
        return totp.recovery_code_hash(
            self.code_secret, self.code_purpose, f"{owner_id}:{normalized}"
        )

    async def _live(self, db: AsyncSession, owner_id: uuid.UUID) -> _Factor | None:
        f = self.factors.c
        row = (
            await db.execute(
                select(f.id, f.secret_ciphertext, f.confirmed_at).where(
                    f[self.owner] == owner_id, f.kind == TOTP, f.disabled_at.is_(None)
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return _Factor(row.id, row.secret_ciphertext, row.confirmed_at is not None)

    def _secret(self, keyring: KeyRing, factor: _Factor) -> str | None:
        try:
            return keyring.decrypt(
                factor.secret_ciphertext, associated_data=self._associated(factor.id)
            ).decode()
        except DecryptionError:
            logger.error("mfa.factor_undecryptable", extra={"factor_id": str(factor.id)})
            return None

    async def enabled(self, db: AsyncSession, owner_id: uuid.UUID) -> bool:
        factor = await self._live(db, owner_id)
        return factor is not None and factor.confirmed

    async def start_enrolment(
        self,
        db: AsyncSession,
        owner_id: uuid.UUID,
        *,
        keyring: KeyRing,
        account: str,
        now: datetime,
    ) -> Enrolment:
        """A new unconfirmed factor (replacing an unconfirmed one)."""
        live = await self._live(db, owner_id)
        if live is not None and live.confirmed:
            raise MfaAlreadyEnabledError()
        if live is not None:
            await self._disable_factor(db, live.id, "replaced", now)
        factor_id = new_id()
        secret = totp.new_secret()
        await db.execute(
            insert(self.factors).values(
                id=factor_id,
                **{self.owner: owner_id},
                kind=TOTP,
                secret_ciphertext=keyring.encrypt(
                    secret.encode(), associated_data=self._associated(factor_id)
                ),
            )
        )
        return Enrolment(secret, totp.provisioning_uri(secret, account))

    async def confirm_enrolment(
        self,
        db: AsyncSession,
        owner_id: uuid.UUID,
        code: str,
        *,
        keyring: KeyRing,
        now: datetime,
    ) -> list[str] | None:
        """Confirm the unconfirmed factor with a first code; recovery codes, or ``None``."""
        factor = await self._live(db, owner_id)
        if factor is None or factor.confirmed:
            return None
        secret = self._secret(keyring, factor)
        step = totp.matching_step(secret, code, now) if secret else None
        if step is None:
            return None
        f = self.factors.c
        confirmed = await db.execute(
            update(self.factors)
            .where(f.id == factor.id, f.confirmed_at.is_(None), f.disabled_at.is_(None))
            .values(confirmed_at=now, last_used_step=step, updated_at=func.now())
        )
        if _rowcount(confirmed) != 1:
            return None
        return await self.replace_recovery_codes(db, owner_id, now=now)

    async def verify_totp(
        self, db: AsyncSession, owner_id: uuid.UUID, code: str, *, keyring: KeyRing, now: datetime
    ) -> bool:
        factor = await self._live(db, owner_id)
        if factor is None or not factor.confirmed:
            return False
        secret = self._secret(keyring, factor)
        step = totp.matching_step(secret, code, now) if secret else None
        if step is None:
            return False
        f = self.factors.c
        accepted = await db.execute(
            update(self.factors)
            .where(
                f.id == factor.id,
                f.disabled_at.is_(None),
                f.confirmed_at.is_not(None),
                (f.last_used_step.is_(None)) | (f.last_used_step < step),
            )
            .values(last_used_step=step, updated_at=func.now())
        )
        return _rowcount(accepted) == 1

    async def use_recovery_code(
        self, db: AsyncSession, owner_id: uuid.UUID, code: str, *, now: datetime
    ) -> bool:
        code_hash = self.code_hash(owner_id, code)
        if code_hash is None or not await self.enabled(db, owner_id):
            return False
        c = self.codes.c
        used = await db.execute(
            update(self.codes)
            .where(
                c[self.owner] == owner_id,
                c.code_hash == code_hash,
                c.used_at.is_(None),
                c.invalidated_at.is_(None),
            )
            .values(used_at=now, updated_at=func.now())
        )
        return _rowcount(used) == 1

    async def replace_recovery_codes(
        self, db: AsyncSession, owner_id: uuid.UUID, *, now: datetime
    ) -> list[str]:
        """Invalidate every open code and issue new ones (returned once)."""
        await self._invalidate_codes(db, owner_id, now)
        codes = totp.new_recovery_codes()
        await db.execute(
            insert(self.codes),
            [
                {"id": new_id(), self.owner: owner_id, "code_hash": self.code_hash(owner_id, code)}
                for code in codes
            ],
        )
        return codes

    async def remaining_codes(self, db: AsyncSession, owner_id: uuid.UUID) -> int:
        c = self.codes.c
        count = await db.scalar(
            select(func.count()).where(
                c[self.owner] == owner_id, c.used_at.is_(None), c.invalidated_at.is_(None)
            )
        )
        return int(count or 0)

    async def disable(
        self, db: AsyncSession, owner_id: uuid.UUID, *, reason: str, now: datetime
    ) -> int:
        """Disable the live factor and invalidate the recovery codes; factors disabled."""
        f = self.factors.c
        result = await db.execute(
            update(self.factors)
            .where(f[self.owner] == owner_id, f.disabled_at.is_(None))
            .values(disabled_at=now, disabled_reason=reason, updated_at=func.now())
        )
        await self._invalidate_codes(db, owner_id, now)
        return _rowcount(result)

    async def _disable_factor(
        self, db: AsyncSession, factor_id: uuid.UUID, reason: str, now: datetime
    ) -> None:
        f = self.factors.c
        await db.execute(
            update(self.factors)
            .where(f.id == factor_id, f.disabled_at.is_(None))
            .values(disabled_at=now, disabled_reason=reason, updated_at=func.now())
        )

    async def _invalidate_codes(self, db: AsyncSession, owner_id: uuid.UUID, now: datetime) -> None:
        c = self.codes.c
        await db.execute(
            update(self.codes)
            .where(c[self.owner] == owner_id, c.used_at.is_(None), c.invalidated_at.is_(None))
            .values(invalidated_at=now, updated_at=func.now())
        )
