import { notFound } from "next/navigation";

import { EnquiryPage } from "@/features/enquiry/EnquiryPage";
import type { EnquiryFormWire } from "@/lib/api/public-enquiry";
import { publicSiteRead } from "@/lib/api/public-site-read";

import type { Metadata } from "next";

// Internal rewrite target of https://<slug>.<site domain>/enquiry (src/proxy.ts;
// Phase 02-4, ADR-0024, INC-27). Never reachable directly: the proxy answers
// /sites/* with 404. The [site] segment only routes the request; the
// institute is resolved by the API from this request's Host, and only a
// verified, active address is served (anything else is RESOURCE-02).

export const dynamic = "force-dynamic";

async function read() {
  return publicSiteRead<EnquiryFormWire>("/enquiry-form");
}

export async function generateMetadata(): Promise<Metadata> {
  const result = await read();
  if (result.kind !== "ok") return { title: "Enquiry" };
  return {
    title: `Enquiry · ${result.data.institute_name}`,
    description: `Ask ${result.data.institute_name} about its maritime courses.`,
  };
}

export default async function SiteEnquiryPage() {
  const result = await read();
  if (result.kind === "not-found") notFound();
  return result.kind === "ok" ? (
    <EnquiryPage kind="ok" form={result.data} />
  ) : (
    <EnquiryPage kind="error" reference={result.reference} />
  );
}
