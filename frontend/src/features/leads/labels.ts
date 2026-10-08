import type { Tone } from "@/design-system/components";
import type {
  FollowUpKind,
  LeadSource,
  LeadStatus,
} from "@/lib/api/admissions";

// Lead management copy (Phase 02-1; GROW-08/09, ADM-02). Display only: the
// server owns every rule (allowed transitions, reasons, eligibility).

export const LEADS_PATH = "/app/admissions/leads";
export const LEAD_READ = "lead.read";
export const LEAD_CREATE = "lead.create";
export const LEAD_UPDATE = "lead.update";
export const LEAD_ASSIGN = "lead.assign";
export const COURSE_READ = "course.read";

export const leadPath = (id: string) => `${LEADS_PATH}/${id}`;

/** Open statuses in pipeline order: the board's columns. */
export const PIPELINE: LeadStatus[] = [
  "NEW",
  "CONTACTED",
  "QUALIFIED",
  "COUNSELLING",
  "INTERESTED",
];

export const STATUS_LABEL: Record<LeadStatus, string> = {
  NEW: "New",
  CONTACTED: "Contacted",
  QUALIFIED: "Qualified",
  COUNSELLING: "Counselling",
  INTERESTED: "Ready to apply",
  APPLICATION: "Application",
  ADMITTED: "Admitted",
  NOT_ELIGIBLE: "Not eligible",
  LOST: "Lost",
  DEFERRED: "Deferred",
  DUPLICATE: "Duplicate",
};

export const STATUS_TONE: Record<LeadStatus, Tone> = {
  NEW: "info",
  CONTACTED: "neutral",
  QUALIFIED: "neutral",
  COUNSELLING: "neutral",
  INTERESTED: "success",
  APPLICATION: "success",
  ADMITTED: "success",
  NOT_ELIGIBLE: "warning",
  LOST: "error",
  DEFERRED: "warning",
  DUPLICATE: "neutral",
};

export const SOURCE_LABEL: Record<LeadSource, string> = {
  WEBSITE: "Website",
  WHATSAPP: "WhatsApp",
  PHONE: "Phone call",
  WALK_IN: "Walk-in",
  INSTAGRAM: "Instagram",
  FACEBOOK: "Facebook",
  YOUTUBE: "YouTube",
  GOOGLE: "Google",
  REFERRAL: "Referral",
  EDUCATION_PORTAL: "Education portal",
  OTHER: "Other",
};

export const FOLLOW_UP_KIND_LABEL: Record<FollowUpKind, string> = {
  CALL: "Call",
  WHATSAPP: "WhatsApp",
  EMAIL: "Email",
  MEETING: "Meeting",
  VISIT: "Campus visit",
  OTHER: "Other",
};

export const FIELD_LABEL: Record<string, string> = {
  full_name: "name",
  mobile: "mobile",
  email: "email",
  source: "source",
  interested_course_id: "course",
  date_of_birth: "date of birth",
  city: "city",
  highest_qualification: "qualification",
};

export const options = <K extends string>(labels: Record<K, string>) =>
  (Object.keys(labels) as K[]).map((id) => ({ id, label: labels[id] }));
