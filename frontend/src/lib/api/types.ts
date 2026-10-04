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
