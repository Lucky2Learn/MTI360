import type { Tone } from "@/design-system/components";
import type {
  ApplicationStatus,
  DocumentStatus,
  DocumentType,
  SubmitRequirement,
} from "@/lib/api/admissions";

// Applications, documents and students copy (Phase 02-2; ADM-05…ADM-14,
// ADR-0021). Display only: the server owns every rule (moves, reasons,
// completeness, document decisions, admission).

export const APPLICATIONS_PATH = "/app/admissions/applications";
export const DOCUMENTS_PATH = "/app/admissions/documents";
export const STUDENTS_PATH = "/app/admissions/students";
export const APPLICATION_READ = "application.read";
export const APPLICATION_CREATE = "application.create";
export const APPLICATION_UPDATE = "application.update";
export const APPLICATION_REVIEW = "application.review";
export const DOCUMENT_READ = "document.read";
export const DOCUMENT_UPLOAD = "document.upload";
export const DOCUMENT_VERIFY = "document.verify";
export const ADMISSION_APPROVE = "admission.approve";
export const STUDENT_READ = "student.read";

export const applicationPath = (id: string) => `${APPLICATIONS_PATH}/${id}`;
export const applicationStepPath = (id: string, step: string) =>
  `${APPLICATIONS_PATH}/${id}/edit?step=${step}`;
export const studentPath = (id: string) => `${STUDENTS_PATH}/${id}`;
export const downloadPath = (documentId: string) =>
  `/api/v1/documents/${documentId}/download`;

export const STATUS_LABEL: Record<ApplicationStatus, string> = {
  DRAFT: "Draft",
  SUBMITTED: "Submitted",
  UNDER_REVIEW: "Under review",
  DOCUMENT_VERIFICATION: "Document verification",
  ELIGIBLE: "Eligible",
  CORRECTION_REQUIRED: "Correction required",
  APPROVED: "Approved",
  ADMITTED: "Admitted",
  REJECTED: "Rejected",
  NOT_ELIGIBLE: "Not eligible",
};

export const STATUS_TONE: Record<ApplicationStatus, Tone> = {
  DRAFT: "neutral",
  SUBMITTED: "info",
  UNDER_REVIEW: "info",
  DOCUMENT_VERIFICATION: "info",
  ELIGIBLE: "info",
  CORRECTION_REQUIRED: "warning",
  APPROVED: "success",
  ADMITTED: "success",
  REJECTED: "error",
  NOT_ELIGIBLE: "warning",
};

/** Review decisions as the reviewer reads them (the server lists what is allowed). */
export const DECISION_LABEL: Partial<Record<ApplicationStatus, string>> = {
  UNDER_REVIEW: "Start review",
  APPROVED: "Approve",
  CORRECTION_REQUIRED: "Request correction",
  REJECTED: "Reject",
  NOT_ELIGIBLE: "Not eligible",
};

export const STATUS_FILTERS: ApplicationStatus[] = [
  "DRAFT",
  "SUBMITTED",
  "UNDER_REVIEW",
  "CORRECTION_REQUIRED",
  "APPROVED",
  "ADMITTED",
  "REJECTED",
  "NOT_ELIGIBLE",
];

export const REQUIREMENT_LABEL: Record<SubmitRequirement, string> = {
  full_name: "Applicant's name",
  date_of_birth: "Date of birth",
  highest_qualification: "Highest qualification",
  contact: "A mobile number or an email",
  declaration: "The applicant's declaration",
};

export const DOCUMENT_TYPE_LABEL: Record<DocumentType, string> = {
  PASSPORT: "Passport",
  CDC: "CDC (Continuous Discharge Certificate)",
  INDOS: "INDoS certificate",
  MARKSHEET_10: "10th marksheet",
  MARKSHEET_12: "12th marksheet",
  MEDICAL_CERTIFICATE: "Medical certificate",
  PHOTO: "Photograph",
  ID_PROOF: "Identity proof",
  OTHER: "Other document",
};

export const DOCUMENT_STATUS_LABEL: Record<DocumentStatus, string> = {
  UPLOADED: "Uploaded",
  UNDER_REVIEW: "Awaiting verification",
  VERIFIED: "Verified",
  REJECTED: "Rejected",
};

export const DOCUMENT_STATUS_TONE: Record<DocumentStatus, Tone> = {
  UPLOADED: "neutral",
  UNDER_REVIEW: "info",
  VERIFIED: "success",
  REJECTED: "error",
};

export const DETAIL_FIELD_LABEL: Record<string, string> = {
  full_name: "name",
  date_of_birth: "date of birth",
  mobile: "mobile",
  email: "email",
  address: "address",
  city: "city",
  state: "state",
  postal_code: "postal code",
  highest_qualification: "highest qualification",
  education_details: "education details",
  indos_number: "INDoS number",
  cdc_number: "CDC number",
  eligibility_notes: "eligibility notes",
  course_id: "course",
  campus_id: "campus",
  declaration: "declaration",
};

/** "2.4 MB" / "320 KB" for file sizes (display only). */
export function fileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
