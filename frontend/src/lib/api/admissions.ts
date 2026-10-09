// Hand-typed contracts of the course and lead API (Phase 02-1; ADR-0020 §13)
// and of applications, documents and students (Phase 02-2; ADR-0021 §9).
// They mirror backend/app/modules/{courses,leads,applications,documents,
// students} field for field and contain only what the UI reads. Success responses are wrapped as { data, meta } (backend
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
  | "NOTE"
  | "APPLICATION_STARTED";

/** `ActivityOut`. `details` holds code-chosen keys (statuses, field names, names). */
export type ActivityWire = {
  id: string;
  kind: ActivityKind;
  actor: { display_name: string } | null;
  details: Record<string, unknown>;
  body: string | null;
  created_at: string;
};

// --- Phase 02-2: applications, documents, students -----------------------------

export type ApplicationStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "UNDER_REVIEW"
  | "DOCUMENT_VERIFICATION"
  | "ELIGIBLE"
  | "CORRECTION_REQUIRED"
  | "APPROVED"
  | "ADMITTED"
  | "REJECTED"
  | "NOT_ELIGIBLE";

/** Fields that block submission (`missing_for_submit`). */
export type SubmitRequirement =
  | "full_name"
  | "date_of_birth"
  | "highest_qualification"
  | "contact"
  | "declaration";

/** `ApplicationOut`. */
export type ApplicationWire = {
  id: string;
  number: string;
  status: ApplicationStatus;
  status_reason: string | null;
  status_changed_at: string;
  lead: { id: string; full_name: string; status: LeadStatus } | null;
  course: { id: string; code: string; name: string; status: CourseStatus };
  campus: { id: string; code: string; name: string };
  owner: { display_name: string } | null;
  created_by: { display_name: string } | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  reviewed_by: { display_name: string } | null;
  declared_at: string | null;
  declared_by: { display_name: string } | null;
  full_name: string;
  date_of_birth: string | null;
  mobile: string | null;
  email: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  highest_qualification: string | null;
  education_details: string | null;
  indos_number: string | null;
  cdc_number: string | null;
  eligibility_notes: string | null;
  documents: { total: number; verified: number; pending: number };
  editable: boolean;
  missing_for_submit: SubmitRequirement[];
  review_options: { to_status: ApplicationStatus; requires_reason: boolean }[];
  admission: {
    id: string;
    admission_number: string;
    student_id: string;
    student_number: string;
    student_visible: boolean;
  } | null;
  created_at: string;
  updated_at: string;
  version: number;
};

/** `ApplicationListItem`. */
export type ApplicationListItemWire = {
  id: string;
  number: string;
  full_name: string;
  status: ApplicationStatus;
  lead_id: string | null;
  course_code: string;
  course_name: string;
  campus_id: string;
  campus_code: string;
  owner_name: string | null;
  documents_pending: number;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
  version: number;
};

export type ApplicationActivityKind =
  | "CREATED"
  | "UPDATED"
  | "SUBMITTED"
  | "STATUS_CHANGED"
  | "DOCUMENT_UPLOADED"
  | "DOCUMENT_VERIFIED"
  | "DOCUMENT_REJECTED"
  | "ADMITTED";

/** `ApplicationActivityOut` (no notes on applications). */
export type ApplicationActivityWire = {
  id: string;
  kind: ApplicationActivityKind;
  actor: { display_name: string } | null;
  details: Record<string, unknown>;
  created_at: string;
};

/** `StudentCandidate`: students the approver may link explicitly. */
export type StudentCandidateWire = {
  id: string;
  student_number: string;
  full_name: string;
  date_of_birth: string | null;
  campus_code: string;
  created_at: string;
  matched_on: ("mobile" | "email")[];
};

export type DocumentType =
  | "PASSPORT"
  | "CDC"
  | "INDOS"
  | "MARKSHEET_10"
  | "MARKSHEET_12"
  | "MEDICAL_CERTIFICATE"
  | "PHOTO"
  | "ID_PROOF"
  | "OTHER";
export type DocumentStatus =
  "UPLOADED" | "UNDER_REVIEW" | "VERIFIED" | "REJECTED";

/** `DocumentOut`. Never an object key, checksum or URL. */
export type DocumentWire = {
  id: string;
  application_id: string;
  document_type: DocumentType;
  status: DocumentStatus;
  rejection_reason: string | null;
  file_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_by: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  replaces_document_id: string | null;
  current: boolean;
  replaced_at: string | null;
  created_at: string;
  version: number;
};

/** `QueueItem` (the ADM-09 verification queue). */
export type QueueItemWire = {
  id: string;
  application_id: string;
  application_number: string;
  applicant_name: string;
  application_status: ApplicationStatus;
  course_code: string;
  campus_code: string;
  document_type: DocumentType;
  status: DocumentStatus;
  file_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_by: string | null;
  created_at: string;
  version: number;
};

/** `StudentListItem`. */
export type StudentListItemWire = {
  id: string;
  student_number: string;
  full_name: string;
  mobile: string | null;
  email: string | null;
  status: "ACTIVE";
  campus_id: string;
  campus_code: string;
  admissions: number;
  latest_course: string | null;
  created_at: string;
};

/** `StudentOut` (Student 360). */
export type StudentWire = {
  id: string;
  student_number: string;
  status: "ACTIVE";
  full_name: string;
  date_of_birth: string | null;
  mobile: string | null;
  email: string | null;
  city: string | null;
  home_campus: { id: string; code: string; name: string };
  created_by: { display_name: string } | null;
  admissions: {
    id: string;
    admission_number: string;
    status: "ADMITTED";
    application_id: string;
    application_number: string;
    course_id: string;
    course_code: string;
    course_name: string;
    course_category: CourseCategory;
    campus: { id: string; code: string; name: string };
    approved_at: string;
    approved_by: { display_name: string } | null;
  }[];
  created_at: string;
  updated_at: string;
  version: number;
};

/** `StudentDocument`. */
export type StudentDocumentWire = {
  id: string;
  application_id: string;
  application_number: string;
  document_type: DocumentType;
  status: DocumentStatus;
  file_name: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
};

/** `TimelineEntry`: the Student 360 history (lead and application activity). */
export type TimelineEntryWire = {
  id: string;
  source: "lead" | "application";
  kind: string;
  actor: { display_name: string } | null;
  details: Record<string, unknown>;
  body: string | null;
  created_at: string;
};
