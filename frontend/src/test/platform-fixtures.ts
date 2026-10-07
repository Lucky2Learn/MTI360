import type { PlatformSessionWire } from "@/lib/api/types";

// Platform session fixtures for frontend tests (T01-09B). Realistic sample
// data (CLAUDE.md §61); never used by application code.

export const PLATFORM_CSRF = "platform-csrf-for-tests-only";

/** The T01 Super Admin baseline (PLATFORM_ROLE_PERMISSIONS). */
export const SUPER_ADMIN_PERMISSIONS = [
  "audit.read",
  "platform_user.create",
  "platform_user.reactivate",
  "platform_user.read",
  "platform_user.suspend",
  "platform_user.update",
  "tenant.create",
  "tenant.reactivate",
  "tenant.read",
  "tenant.suspend",
];

/** A full (MFA-verified) platform session; defaults to a Super Admin. */
export function platformSession(
  overrides: Partial<PlatformSessionWire> = {},
): PlatformSessionWire {
  return {
    status: "authenticated",
    user: {
      display_name: "Meera Iyer",
      email: "meera.iyer@mti360.example",
    },
    permissions: SUPER_ADMIN_PERMISSIONS,
    roles: ["SUPER_ADMIN"],
    mfa: {
      enrolled: true,
      verified_at: "2026-10-07T09:30:00Z",
      step_up_expires_at: "2026-10-07T09:40:00Z",
      recovery_codes_remaining: 10,
    },
    csrf_token: PLATFORM_CSRF,
    ...overrides,
  };
}

/** The login response: an MFA-pending session (no user, no permissions). */
export function pendingPlatformSession(
  status: "mfa_required" | "mfa_enrolment_required",
  csrf = "pending-platform-csrf",
): PlatformSessionWire {
  return {
    status,
    user: null,
    permissions: [],
    roles: [],
    mfa: {
      enrolled: status === "mfa_required",
      verified_at: null,
      step_up_expires_at: null,
      recovery_codes_remaining: null,
    },
    csrf_token: csrf,
  };
}

export const RECOVERY_CODES = [
  "abcde-fghij",
  "klmno-pqrst",
  "uvwxy-z2345",
  "67abc-defgh",
  "ijklm-nopqr",
  "stuvw-xyz23",
  "4567a-bcdef",
  "ghijk-lmnop",
  "qrstu-vwxyz",
  "23456-7abcd",
];

/** A fake base32 setup key and its otpauth URI (test values only). */
export const ENROLMENT = {
  secret: "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
  otpauth_uri:
    "otpauth://totp/MTI%20360:meera.iyer%40mti360.example?secret=JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP&issuer=MTI+360&algorithm=SHA1&digits=6&period=30",
};
