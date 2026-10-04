import type {
  CampusWire,
  InstituteWire,
  SessionStatus,
  SessionWire,
} from "@/lib/api/types";

// Session fixtures for frontend tests (T01-09A). Realistic maritime sample
// data (CLAUDE.md §61); never used by application code.

export const INSTITUTES = {
  coastal: {
    id: "7d0c3c2e-6c55-4b8a-9f0e-2c1f4a7b9d01",
    name: "Coastal Maritime Training Institute",
    is_trial: false,
  },
  harbour: {
    id: "1b9e4f6a-3d2c-4e8f-a7b5-6c0d9e8f7a02",
    name: "Harbour Nautical Academy",
    is_trial: true,
  },
} satisfies Record<string, InstituteWire>;

export const CAMPUSES = {
  kochi: {
    id: "a3f1c2d4-5b6e-4f70-8a9b-0c1d2e3f4a11",
    name: "Kochi Campus",
    code: "KOC",
  },
  vizag: {
    id: "b4e2d3c5-6a7f-4081-9bac-1d2e3f4a5b22",
    name: "Visakhapatnam Campus",
    code: "VTZ",
  },
} satisfies Record<string, CampusWire>;

export const CSRF_TOKEN = "csrf-token-for-tests-only";

/** A session read; defaults to a ready member with one institute and campus. */
export function readySession(
  overrides: Partial<SessionWire> = {},
): SessionWire {
  return {
    status: "ready",
    user: {
      display_name: "Ananya Rao",
      email: "ananya.rao@coastal-maritime.example",
    },
    active_institute: INSTITUTES.coastal,
    institutes: [INSTITUTES.coastal],
    active_campus: CAMPUSES.kochi,
    campus_options: [CAMPUSES.kochi],
    all_campuses_allowed: false,
    campus_selection_required: false,
    csrf_token: CSRF_TOKEN,
    permissions: [],
    roles: [{ name: "Admissions Counsellor", is_system: false }],
    mfa_enabled: false,
    ...overrides,
  };
}

/** A session in `status` with the matching institute/campus fields. */
export function sessionIn(
  status: SessionStatus,
  overrides: Partial<SessionWire> = {},
): SessionWire {
  switch (status) {
    case "institute_selection_required":
      return readySession({
        status,
        active_institute: null,
        institutes: [INSTITUTES.coastal, INSTITUTES.harbour],
        active_campus: null,
        campus_options: [],
        permissions: [],
        roles: [],
        ...overrides,
      });
    case "campus_selection_required":
      return readySession({
        status,
        active_campus: null,
        campus_options: [CAMPUSES.kochi, CAMPUSES.vizag],
        campus_selection_required: true,
        ...overrides,
      });
    case "mfa_required":
      return readySession({
        status,
        active_institute: null,
        institutes: [],
        active_campus: null,
        campus_options: [],
        mfa_enabled: true,
        ...overrides,
      });
    default:
      return readySession({ status, ...overrides });
  }
}
