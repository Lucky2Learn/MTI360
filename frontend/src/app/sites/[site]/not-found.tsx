import { SiteNotFound } from "@/features/enquiry/SiteNotFound";
import type { EnquiryFormWire } from "@/lib/api/public-enquiry";
import { publicSiteRead } from "@/lib/api/public-site-read";

import type { Metadata } from "next";

// Not-found view of the hosted institute pages (Phase 02-4, ADR-0024), with
// status 404. The institute is resolved by the API from this request's Host,
// exactly as for its enquiry page: only a verified, active address returns a
// name. Anything else (unknown, inactive, unverified, unreachable) gets the
// neutral page, so it reveals nothing about any institute.

export const metadata: Metadata = {
  title: "Page not found",
  robots: { index: false, follow: false },
};

export default async function SiteNotFoundPage() {
  const result = await publicSiteRead<EnquiryFormWire>("/enquiry-form");
  return (
    <SiteNotFound
      institute={result.kind === "ok" ? result.data.institute_name : null}
    />
  );
}
