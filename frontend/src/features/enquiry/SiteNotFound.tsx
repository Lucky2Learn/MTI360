"use client";

import { Button } from "@/design-system/components";
import type { Navigation } from "@/shells/navigation";
import { PublicSiteShell } from "@/shells/PublicSiteShell";

// Not-found page of the hosted institute pages (Phase 02-4, ADR-0024; T18).
// Rendered with status 404 for any path of an institute address other than
// its pages, and for a host that is not an institute address.
// - `institute` is the name the API returned for the request's host, which it
//   does only for a verified, active address of a TRIAL or ACTIVE institute.
//   Then the page carries the institute's name and links to its enquiry page.
// - `null` (unknown, inactive or unverified host, or the API unreachable):
//   a neutral page that names no institute and links nowhere.
// Never staff or platform navigation. Logos: none exists in the data model
// yet (the institute's own branding comes with the Phase 14 website).

const SITE_NAVIGATION: Navigation = [
  {
    id: "site",
    items: [{ id: "enquiry", label: "Enquiry", href: "/enquiry" }],
  },
];

export function SiteNotFound({ institute }: { institute: string | null }) {
  return (
    <PublicSiteShell
      siteLabel={institute ?? "Institute website"}
      homeHref={institute ? "/enquiry" : "/"}
      navigation={institute ? SITE_NAVIGATION : []}
      navigationLabel="Website"
      footerNote={
        institute
          ? `${institute} · Website hosted by MTI 360.`
          : "Website hosted by MTI 360."
      }
    >
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-12 tablet:px-6 desktop:py-16">
        <p className="text-body-sm font-semibold text-accent-maritime">404</p>
        <h1 className="text-page-title text-text-primary">Page not found</h1>
        {institute ? (
          <>
            <p className="text-body text-text-secondary">
              This page isn&apos;t available on the {institute} website. You can
              still ask the institute about its courses.
            </p>
            <div>
              <Button href="/enquiry">Ask about a course</Button>
            </div>
          </>
        ) : (
          <p className="text-body text-text-secondary">
            This website address isn&apos;t available. Check the address, or
            contact the institute directly.
          </p>
        )}
      </div>
    </PublicSiteShell>
  );
}
