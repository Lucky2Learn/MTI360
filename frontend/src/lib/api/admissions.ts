// Hand-typed contracts of the course and lead API (Phase 02-1; ADR-0020 §13).
// They mirror backend/app/modules/courses/router.py and
// backend/app/modules/leads/schemas.py field for field and contain only what
// the UI reads. Success responses are wrapped as { data, meta } (backend
// Envelope / ListEnvelope).

export type CourseCategory = "PRE_SEA" | "POST_SEA" | "OTHER";
export type CourseStatus = "DRAFT" | "ACTIVE" | "ARCHIVED";
export type DurationUnit = "DAYS" | "WEEKS" | "MONTHS" | "YEARS";

/** `CourseOut`. */
export type CourseWire = {
  id: string;
  code: string;
  name: string;
  category: CourseCategory;
  status: CourseStatus;
  description: string | null;
  duration_value: number | null;
  duration_unit: DurationUnit | null;
  eligibility_summary: string | null;
  created_at: string;
  updated_at: string;
  version: number;
};

export type LeadStatus =
  | "NEW"
  | "CONTACTED"
  | "QUALIFIED"
  | "COUNSELLING"
  | "INTERESTED"
  | "APPLICATION"
  | "ADMITTED"
  | "NOT_ELIGIBLE"
  | "LOST"
  | "DEFERRED"
  | "DUPLICATE";

export type LeadSource =
  | "WEBSITE"
  | "WHATSAPP"
  | "PHONE"
  | "WALK_IN"
  | "INSTAGRAM"
  | "FACEBOOK"
  | "YOUTUBE"
  | "GOOGLE"
  | "REFERRAL"
  | "EDUCATION_PORTAL"
  | "OTHER";

/** A status the caller may move a lead to now (the server's rule). */
export type TransitionOptionWire = {
  to_status: LeadStatus;
  requires_reason: boolean;
  requires_duplicate_target: boolean;
};

/** `LeadOut`. */
export type LeadWire = {
  id: string;
  full_name: string;
  mobile: string | null;
  email: string | null;
  date_of_birth: string | null;
  city: string | null;
  highest_qualification: string | null;
  source: LeadSource;
  status: LeadStatus;
  status_reason: string | null;
  status_changed_at: string;
  interested_course: {
    id: string;
    code: string;
    name: string;
    status: CourseStatus;
  } | null;
  campus: { id: string; code: string; name: string } | null;
  owner: {
    membership_id: string;
    display_name: string;
    active: boolean;
  } | null;
  duplicate_of: { id: string; full_name: string } | null;
  next_follow_up_at: string | null;
  overdue_follow_ups: number;
  created_by: { display_name: string } | null;
  transitions: TransitionOptionWire[];
  created_at: string;
  updated_at: string;
  version: number;
};

/** `LeadListItem` (list and board). */
export type LeadListItemWire = {
  id: string;
  full_name: string;
  mobile: string | null;
  email: string | null;
  status: LeadStatus;
  source: LeadSource;
  interested_course: { code: string; name: string } | null;
  campus: { id: string; code: string } | null;
  owner: { membership_id: string; display_name: string } | null;
  next_follow_up_at: string | null;
  overdue_follow_ups: number;
  transitions: TransitionOptionWire[];
  created_at: string;
  updated_at: string;
  version: number;
};

/** `DuplicateCandidate`: only leads the caller may read. */
export type DuplicateCandidateWire = {
  id: string;
  full_name: string;
  status: LeadStatus;
  course_name: string | null;
  campus_name: string | null;
  owner_name: string | null;
  created_at: string;
  matched_on: ("mobile" | "email")[];
};

export type AssigneeWire = { membership_id: string; display_name: string };

export type FollowUpKind =
  "CALL" | "WHATSAPP" | "EMAIL" | "MEETING" | "VISIT" | "OTHER";
export type FollowUpStatus = "OPEN" | "DONE" | "CANCELLED";

/** `FollowUpOut`. */
export type FollowUpWire = {
  id: string;
  lead_id: string;
  due_at: string;
  kind: FollowUpKind;
  note: string | null;
  outcome: string | null;
  status: FollowUpStatus;
  overdue: boolean;
  assignee: {
    membership_id: string;
    display_name: string;
    active: boolean;
  } | null;
  completed_at: string | null;
  completed_by: { display_name: string } | null;
  created_at: string;
  version: number;
};

export type ActivityKind =
  | "CREATED"
  | "UPDATED"
  | "STATUS_CHANGED"
  | "ASSIGNED"
  | "FOLLOW_UP_SCHEDULED"
  | "FOLLOW_UP_COMPLETED"
  | "FOLLOW_UP_CANCELLED"
  | "NOTE";

/** `ActivityOut`. `details` holds code-chosen keys (statuses, field names, names). */
export type ActivityWire = {
  id: string;
  kind: ActivityKind;
  actor: { display_name: string } | null;
  details: Record<string, unknown>;
  body: string | null;
  created_at: string;
};
