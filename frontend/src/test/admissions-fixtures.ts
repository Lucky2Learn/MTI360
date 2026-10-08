import type {
  ActivityWire,
  CourseWire,
  FollowUpWire,
  LeadListItemWire,
  LeadWire,
  TransitionOptionWire,
} from "@/lib/api/admissions";
import type { ReadResult } from "@/lib/api/server-read";

// Course and lead fixtures for frontend tests (Phase 02-1). Realistic
// maritime sample data (CLAUDE.md §61); contacts are fictitious
// (.example emails, the 90000 10xxx range). Never used by application code.

export const IDS = {
  gpr: "0199a1b2-0000-7000-8000-000000000001",
  dns: "0199a1b2-0000-7000-8000-000000000002",
  ccmc: "0199a1b2-0000-7000-8000-000000000003",
  arjun: "0199a1b2-0000-7000-8000-0000000000a1",
  meera: "0199a1b2-0000-7000-8000-0000000000a2",
  ravi: "0199a1b2-0000-7000-8000-0000000000b1",
  followUp: "0199a1b2-0000-7000-8000-0000000000c1",
} as const;

export const COURSE_PERMISSIONS = ["course.read", "course.manage"];
export const COUNSELLOR = [
  "course.read",
  "lead.read",
  "lead.create",
  "lead.update",
];
export const MANAGER = [
  ...COURSE_PERMISSIONS,
  "lead.read",
  "lead.create",
  "lead.update",
  "lead.assign",
];

export function course(overrides: Partial<CourseWire> = {}): CourseWire {
  return {
    id: IDS.gpr,
    code: "GPR",
    name: "GP Rating",
    category: "PRE_SEA",
    status: "ACTIVE",
    description: "Six-month pre-sea rating course.",
    duration_value: 6,
    duration_unit: "MONTHS",
    eligibility_summary: "10th pass with 40% in Science, Maths and English.",
    created_at: "2026-10-01T09:00:00Z",
    updated_at: "2026-10-02T09:00:00Z",
    version: 2,
    ...overrides,
  };
}

const OPEN_MOVES: TransitionOptionWire[] = [
  ["CONTACTED", false, false],
  ["QUALIFIED", false, false],
  ["COUNSELLING", false, false],
  ["INTERESTED", false, false],
  ["NOT_ELIGIBLE", true, false],
  ["LOST", true, false],
  ["DEFERRED", true, false],
  ["DUPLICATE", false, true],
].map(([to, reason, target]) => ({
  to_status: to as TransitionOptionWire["to_status"],
  requires_reason: reason as boolean,
  requires_duplicate_target: target as boolean,
}));

export function leadItem(
  overrides: Partial<LeadListItemWire> = {},
): LeadListItemWire {
  return {
    id: IDS.arjun,
    full_name: "Arjun Nair",
    mobile: "+91 90000 10001",
    email: "arjun.nair@example.com",
    status: "NEW",
    source: "WALK_IN",
    interested_course: { code: "GPR", name: "GP Rating" },
    campus: { id: "a3f1c2d4-5b6e-4f70-8a9b-0c1d2e3f4a11", code: "KOC" },
    owner: { membership_id: IDS.ravi, display_name: "Ravi Menon" },
    next_follow_up_at: "2026-10-09T04:30:00Z",
    overdue_follow_ups: 0,
    transitions: OPEN_MOVES,
    created_at: "2026-10-08T05:00:00Z",
    updated_at: "2026-10-08T05:00:00Z",
    version: 3,
    ...overrides,
  };
}

export function lead(overrides: Partial<LeadWire> = {}): LeadWire {
  return {
    id: IDS.arjun,
    full_name: "Arjun Nair",
    mobile: "+91 90000 10001",
    email: "arjun.nair@example.com",
    date_of_birth: "2007-05-14",
    city: "Kochi",
    highest_qualification: "12th PCM, 68%",
    source: "WALK_IN",
    status: "NEW",
    status_reason: null,
    status_changed_at: "2026-10-08T05:00:00Z",
    interested_course: {
      id: IDS.gpr,
      code: "GPR",
      name: "GP Rating",
      status: "ACTIVE",
    },
    campus: {
      id: "a3f1c2d4-5b6e-4f70-8a9b-0c1d2e3f4a11",
      code: "KOC",
      name: "Kochi Campus",
    },
    owner: {
      membership_id: IDS.ravi,
      display_name: "Ravi Menon",
      active: true,
    },
    duplicate_of: null,
    next_follow_up_at: null,
    overdue_follow_ups: 0,
    created_by: { display_name: "Ananya Rao" },
    transitions: OPEN_MOVES,
    created_at: "2026-10-08T05:00:00Z",
    updated_at: "2026-10-08T05:00:00Z",
    version: 3,
    ...overrides,
  };
}

export function followUp(overrides: Partial<FollowUpWire> = {}): FollowUpWire {
  return {
    id: IDS.followUp,
    lead_id: IDS.arjun,
    due_at: "2026-10-07T04:30:00Z",
    kind: "CALL",
    note: "Discuss DNS sponsorship",
    outcome: null,
    status: "OPEN",
    overdue: true,
    assignee: {
      membership_id: IDS.ravi,
      display_name: "Ravi Menon",
      active: true,
    },
    completed_at: null,
    completed_by: null,
    created_at: "2026-10-06T04:30:00Z",
    version: 1,
    ...overrides,
  };
}

export function activity(overrides: Partial<ActivityWire> = {}): ActivityWire {
  return {
    id: "act-1",
    kind: "CREATED",
    actor: { display_name: "Ananya Rao" },
    details: { source: "WALK_IN", possible_duplicates: 0 },
    body: null,
    created_at: "2026-10-08T05:00:00Z",
    ...overrides,
  };
}

export const ok = <T>(data: T, total?: number): ReadResult<T> => ({
  kind: "ok",
  data,
  page: total === undefined ? null : { limit: 25, offset: 0, total },
});
