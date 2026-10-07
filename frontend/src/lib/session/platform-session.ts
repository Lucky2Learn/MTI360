import type { PlatformSessionWire } from "@/lib/api/types";

// Client platform session state (T01-09B UI contract §8; T01-05 §5 rules).
// Derived from ONE full (MFA-verified) session response and replaced as a
// whole on every re-read — never merged, never persisted, never taken from a
// URL. It drives UX only; the API authorizes every request (CLAUDE.md §10).

export type PlatformSession = {
  user: { displayName: string; email: string };
  /** Opaque permission codes; compared for equality only. */
  permissions: ReadonlySet<string>;
  /** Display only: never used to decide anything (no role gating). */
  roles: string[];
  mfa: {
    enrolled: boolean;
    /** Display only (D9B-7): the low-codes warning. */
    recoveryCodesRemaining: number | null;
  };
  /** In memory only; sent as X-CSRF-Token on unsafe requests. */
  csrfToken: string;
};

/** Recovery codes at or below this count show a warning (D9B-7). */
export const LOW_RECOVERY_CODES = 3;

/**
 * A full session from the wire, or null when the response is not one
 * (an MFA-pending session never becomes a PlatformSession).
 */
export function toPlatformSession(
  wire: PlatformSessionWire,
): PlatformSession | null {
  if (wire.status !== "authenticated" || !wire.user) return null;
  return {
    user: { displayName: wire.user.display_name, email: wire.user.email },
    permissions: new Set(wire.permissions),
    roles: [...wire.roles],
    mfa: {
      enrolled: wire.mfa.enrolled,
      recoveryCodesRemaining: wire.mfa.recovery_codes_remaining,
    },
    csrfToken: wire.csrf_token,
  };
}

export function lowRecoveryCodes(session: PlatformSession): boolean {
  const remaining = session.mfa.recoveryCodesRemaining;
  return remaining !== null && remaining <= LOW_RECOVERY_CODES;
}

const ROLE_LABELS: Record<string, string> = {
  SUPER_ADMIN: "Super Admin",
  PLATFORM_OPERATIONS_ADMIN: "Platform Operations Admin",
  CUSTOMER_SUCCESS_ADMIN: "Customer Success Admin",
  BILLING_ADMIN: "Billing Admin",
  SUPPORT_ADMIN: "Support Admin",
  SECURITY_AUDIT_ADMIN: "Security / Audit Admin",
  AI_PLATFORM_ADMIN: "AI / Platform Admin",
};

/** Display label of a platform role code (CLAUDE.md §11 names; display only). */
export function platformRoleLabel(code: string): string {
  return ROLE_LABELS[code] ?? code;
}
