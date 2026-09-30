# ADR-0012 — Application-Level Encryption of Secrets at Rest

- **Status:** Accepted (T01-00 approval, decisions D4, D9; implementation in T01-06)
- **Date:** 2026-09-30
- **Task:** T01-00 (recorded in T01-01)
- **Related:** [ADR-0010](0010-sessions-credentials-and-csrf.md), [security.md](../architecture/security.md) §4, §9, [environments.md](../architecture/environments.md)

## Context

Most authentication secrets can be stored as one-way hashes: passwords with Argon2id, and session, reset, invitation and recovery tokens with HMAC or Argon2. A TOTP shared secret must be recoverable to verify codes, so it needs reversible encryption with a key that is not in the database. Future provider credentials configured per tenant have the same need.

## Decision

1. **Hash whenever possible; encrypt only what must be recovered.**
2. **AES-256-GCM** through the `cryptography` package (added in T01-06, subject to the dependency cooldown).
   - Ciphertext format: `v1:<key-id>:<nonce>:<ciphertext+tag>`.
   - The row identity is used as associated data, so a ciphertext cannot be moved to another row.
3. **Key material:**
   - `DATA_ENCRYPTION_KEY` holds 32 random bytes, base64-encoded, and is injected by the secret manager.
   - It is validated at startup like the other secrets: required outside development, never a placeholder, never logged.
   - A key ID supports rotation; old keys stay decrypt-only until re-encryption.
   - This is an approved environment change (D9), added in T01-06.
4. **Encryption lives in `app/core/security/encryption.py`.** Plaintext secrets never leave the credential services, never appear in API responses or logs, and are never exported.

## Consequences

- A database leak alone does not reveal TOTP secrets.
- Key rotation is possible without downtime.
- One more required deployed secret.

## Alternatives considered

- **PostgreSQL `pgcrypto`:** the key would travel in SQL, and could appear in statement logs. Rejected.
- **Storing TOTP secrets in plaintext:** rejected.
- **A cloud KMS per request:** stronger isolation but adds a runtime dependency and latency. Envelope encryption with a KMS-managed data key can be introduced later behind the same module.
