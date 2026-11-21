import { apiRequest } from "./client";

// Public enquiry wire types (Phase 02-4, ADR-0024). Mirrors
// backend/app/modules/enquiries/schemas.py with only what the page reads.
// The request never names an institute: the API resolves it from the host
// the browser asked for.

export type EnquiryCourseWire = {
  id: string;
  name: string;
  category: string;
};

/** `EnquiryFormOut`: GET /public/enquiry-form. */
export type EnquiryFormWire = {
  institute_name: string;
  courses: EnquiryCourseWire[];
  consent: { version: string; text: string; retention_months: number };
  privacy_notice: string;
};

/** `EnquiryRequest`: POST /public/enquiries. `website` is the spam trap. */
export type EnquiryRequestWire = {
  full_name: string;
  email: string | null;
  mobile: string | null;
  course_id: string | null;
  message: string | null;
  consent_accepted: boolean;
  consent_version: string;
  website: string;
};

/** Field limits (backend leads/enquiries domain). */
export const ENQUIRY_LIMITS = {
  name: 200,
  email: 254,
  mobile: 32,
  message: 1000,
} as const;

/** 202 with the same body for every accepted enquiry; throws ApiError otherwise. */
export function submitEnquiry(body: EnquiryRequestWire): Promise<void> {
  return apiRequest<void>("/public/enquiries", { method: "POST", body });
}
