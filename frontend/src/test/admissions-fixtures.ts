import type {
  ActivityWire,
  ApplicationActivityWire,
  ApplicationListItemWire,
  ApplicationWire,
  CourseWire,
  DocumentWire,
  QueueItemWire,
  StudentCandidateWire,
  StudentListItemWire,
  StudentWire,
  TimelineEntryWire,
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
  application: "0199a1b2-0000-7000-8000-0000000000d1",
  passport: "0199a1b2-0000-7000-8000-0000000000e1",
  medical: "0199a1b2-0000-7000-8000-0000000000e2",
  student: "0199a1b2-0000-7000-8000-0000000000f1",
  otherStudent: "0199a1b2-0000-7000-8000-0000000000f2",
} as const;

const KOCHI = {
  id: "a3f1c2d4-5b6e-4f70-8a9b-0c1d2e3f4a11",
  code: "KOC",
  name: "Kochi Campus",
};

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

// --- Phase 02-2 -----------------------------------------------------------------

export const ADMISSIONS_COUNSELLOR = [
  ...COUNSELLOR,
  "application.read",
  "application.create",
  "application.update",
  "document.read",
  "document.upload",
  "student.read",
];
export const ADMISSIONS_MANAGER = [
  ...MANAGER,
  "application.read",
  "application.create",
  "application.update",
  "application.review",
  "document.read",
  "document.upload",
  "document.verify",
  "admission.approve",
  "student.read",
];

export function application(
  overrides: Partial<ApplicationWire> = {},
): ApplicationWire {
  return {
    id: IDS.application,
    number: "APP-2026-00012",
    status: "DRAFT",
    status_reason: null,
    status_changed_at: "2026-10-09T05:00:00Z",
    lead: { id: IDS.arjun, full_name: "Arjun Nair", status: "APPLICATION" },
    course: { id: IDS.gpr, code: "GPR", name: "GP Rating", status: "ACTIVE" },
    campus: KOCHI,
    owner: { display_name: "Ravi Menon" },
    created_by: { display_name: "Ravi Menon" },
    submitted_at: null,
    reviewed_at: null,
    reviewed_by: null,
    declared_at: null,
    declared_by: null,
    full_name: "Arjun Nair",
    date_of_birth: null,
    mobile: "+91 90000 10001",
    email: "arjun.nair@example.com",
    address: null,
    city: "Kochi",
    state: null,
    postal_code: null,
    highest_qualification: "12th PCM, 68%",
    education_details: null,
    indos_number: null,
    cdc_number: null,
    eligibility_notes: null,
    documents: { total: 0, verified: 0, pending: 0 },
    editable: true,
    missing_for_submit: ["date_of_birth", "declaration"],
    review_options: [],
    admission: null,
    created_at: "2026-10-09T05:00:00Z",
    updated_at: "2026-10-09T05:00:00Z",
    version: 2,
    ...overrides,
  };
}

export function applicationItem(
  overrides: Partial<ApplicationListItemWire> = {},
): ApplicationListItemWire {
  return {
    id: IDS.application,
    number: "APP-2026-00012",
    full_name: "Arjun Nair",
    status: "SUBMITTED",
    lead_id: IDS.arjun,
    course_code: "GPR",
    course_name: "GP Rating",
    campus_id: KOCHI.id,
    campus_code: "KOC",
    owner_name: "Ravi Menon",
    documents_pending: 2,
    submitted_at: "2026-10-09T06:00:00Z",
    created_at: "2026-10-09T05:00:00Z",
    updated_at: "2026-10-09T06:00:00Z",
    version: 4,
    ...overrides,
  };
}

export function documentWire(
  overrides: Partial<DocumentWire> = {},
): DocumentWire {
  return {
    id: IDS.passport,
    application_id: IDS.application,
    document_type: "PASSPORT",
    status: "UNDER_REVIEW",
    rejection_reason: null,
    file_name: "arjun-passport.pdf",
    content_type: "application/pdf",
    size_bytes: 482_000,
    uploaded_by: "Ravi Menon",
    reviewed_by: null,
    reviewed_at: null,
    replaces_document_id: null,
    current: true,
    replaced_at: null,
    created_at: "2026-10-09T05:30:00Z",
    version: 2,
    ...overrides,
  };
}

export function queueItem(
  overrides: Partial<QueueItemWire> = {},
): QueueItemWire {
  return {
    id: IDS.passport,
    application_id: IDS.application,
    application_number: "APP-2026-00012",
    applicant_name: "Arjun Nair",
    application_status: "SUBMITTED",
    course_code: "GPR",
    campus_code: "KOC",
    document_type: "PASSPORT",
    status: "UNDER_REVIEW",
    file_name: "arjun-passport.pdf",
    content_type: "application/pdf",
    size_bytes: 482_000,
    uploaded_by: "Ravi Menon",
    created_at: "2026-10-09T05:30:00Z",
    version: 2,
    ...overrides,
  };
}

export function applicationActivity(
  overrides: Partial<ApplicationActivityWire> = {},
): ApplicationActivityWire {
  return {
    id: "aact-1",
    kind: "CREATED",
    actor: { display_name: "Ravi Menon" },
    details: { from_lead: true },
    created_at: "2026-10-09T05:00:00Z",
    ...overrides,
  };
}

export function candidate(
  overrides: Partial<StudentCandidateWire> = {},
): StudentCandidateWire {
  return {
    id: IDS.otherStudent,
    student_number: "STU-2025-00031",
    full_name: "Arjun Nair",
    date_of_birth: "2007-05-14",
    campus_code: "KOC",
    created_at: "2025-11-02T05:00:00Z",
    matched_on: ["mobile"],
    ...overrides,
  };
}

export function student(overrides: Partial<StudentWire> = {}): StudentWire {
  return {
    id: IDS.student,
    student_number: "STU-2026-00007",
    status: "ACTIVE",
    full_name: "Arjun Nair",
    date_of_birth: "2007-05-14",
    mobile: "+91 90000 10001",
    email: "arjun.nair@example.com",
    city: "Kochi",
    home_campus: KOCHI,
    created_by: { display_name: "Ananya Rao" },
    admissions: [
      {
        id: "adm-1",
        admission_number: "ADM-2026-00007",
        status: "ADMITTED",
        application_id: IDS.application,
        application_number: "APP-2026-00012",
        course_id: IDS.gpr,
        course_code: "GPR",
        course_name: "GP Rating",
        course_category: "PRE_SEA",
        campus: KOCHI,
        approved_at: "2026-10-12T05:00:00Z",
        approved_by: { display_name: "Ananya Rao" },
      },
    ],
    created_at: "2026-10-12T05:00:00Z",
    updated_at: "2026-10-12T05:00:00Z",
    version: 1,
    ...overrides,
  };
}

export function studentItem(
  overrides: Partial<StudentListItemWire> = {},
): StudentListItemWire {
  return {
    id: IDS.student,
    student_number: "STU-2026-00007",
    full_name: "Arjun Nair",
    mobile: "+91 90000 10001",
    email: "arjun.nair@example.com",
    status: "ACTIVE",
    campus_id: KOCHI.id,
    campus_code: "KOC",
    admissions: 1,
    latest_course: "GP Rating",
    created_at: "2026-10-12T05:00:00Z",
    ...overrides,
  };
}

export function timelineEntry(
  overrides: Partial<TimelineEntryWire> = {},
): TimelineEntryWire {
  return {
    id: "tl-1",
    source: "application",
    kind: "ADMITTED",
    actor: { display_name: "Ananya Rao" },
    details: {
      admission_number: "ADM-2026-00007",
      student_number: "STU-2026-00007",
      student_created: true,
    },
    body: null,
    created_at: "2026-10-12T05:00:00Z",
    ...overrides,
  };
}
