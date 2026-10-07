// Hand-typed contracts of the tenant authentication and session API (T01-09A).
// They mirror backend/app/modules/identity/schemas.py field for field and
// contain only what the UI reads (T01-04 UI contract §15, T01-05 §5).
// Success responses are wrapped as { data, meta } (backend Envelope).

export type SessionStatus =
  | "ready"
  | "institute_selection_required"
  | "campus_selection_required"
  | "mfa_required";

export type InstituteWire = {
  id: string;
  name: string;
  is_trial: boolean;
};

export type CampusWire = {
  id: string;
  name: string;
  code: string;
};

export type RoleWire = {
  name: string;
  is_system: boolean;
};

/** `SessionOut`: GET /session and the login, MFA and switch responses. */
export type SessionWire = {
  status: SessionStatus;
  user: { display_name: string; email: string };
  active_institute: InstituteWire | null;
  institutes: InstituteWire[];
  active_campus: CampusWire | null;
  campus_options: CampusWire[];
  all_campuses_allowed: boolean;
  campus_selection_required: boolean;
  csrf_token: string;
  permissions: string[];
  roles: RoleWire[];
  mfa_enabled: boolean;
};

/** `InvitationPreviewOut` (D19). */
export type InvitationPreviewWire = {
  institute_name: string;
  email_masked: string;
  account: "new" | "existing";
};

// --- Platform realm (T01-09B) -------------------------------------------------
// Hand-typed contracts of the platform authentication and session API. They
// mirror backend/app/modules/platform_identity/schemas.py and admin_schemas.py
// field for field and contain only what the UI reads.

export type PlatformSessionStatus =
  "authenticated" | "mfa_required" | "mfa_enrolment_required";

export type PlatformMfaWire = {
  enrolled: boolean;
  verified_at: string | null;
  /** Display only; the backend decides step-up (D9B-6). */
  step_up_expires_at: string | null;
  recovery_codes_remaining: number | null;
};

/** `PlatformSessionOut`: GET /platform/session and the login/MFA responses. */
export type PlatformSessionWire = {
  status: PlatformSessionStatus;
  /** `null` until MFA is complete. */
  user: { display_name: string; email: string } | null;
  permissions: string[];
  roles: string[];
  mfa: PlatformMfaWire;
  csrf_token: string;
};

/** `MfaEnrolmentOut` (shown once; memory only). */
export type MfaEnrolmentWire = {
  secret: string;
  otpauth_uri: string;
};

/** `MfaEnrolmentConfirmedOut`: recovery codes (once) and the rotated session. */
export type MfaEnrolmentConfirmedWire = {
  recovery_codes: string[];
  session: PlatformSessionWire;
};

/** `RecoveryCodesOut` (shown once; memory only). */
export type RecoveryCodesWire = {
  recovery_codes: string[];
};

/** `PlatformInvitationPreviewOut`: the server-masked email only (D7-3). */
export type PlatformInvitationPreviewWire = {
  email: string;
};
