"use client";

import { ErrorState } from "@/design-system/components";
import type { EnquiryFormWire } from "@/lib/api/public-enquiry";
import type { Navigation } from "@/shells/navigation";
import { PublicSiteShell } from "@/shells/PublicSiteShell";

import { EnquiryForm } from "./EnquiryForm";

// Hosted enquiry page (Phase 02-4, ADR-0024; T18 Public Website template):
// https://<slug>.<site domain>/enquiry. Mobile-first: one column, the form
// below a short introduction, two columns for email and phone from the
// tablet breakpoint. The institute's name is its identity on the page; logos
// and colours come with the Phase 14 website.

const NAVIGATION: Navigation = [
  {
    id: "site",
    items: [{ id: "enquiry", label: "Enquiry", href: "/enquiry" }],
  },
];

export type EnquiryPageProps =
  | { kind: "ok"; form: EnquiryFormWire }
  | { kind: "error"; reference: string | null };

export function EnquiryPage(props: EnquiryPageProps) {
  const institute = props.kind === "ok" ? props.form.institute_name : "Enquiry";
  return (
    <PublicSiteShell
      siteLabel={institute}
      homeHref="/enquiry"
      navigation={NAVIGATION}
      navigationLabel="Website"
      footerNote={
        props.kind === "ok"
          ? `${institute} · Enquiry page hosted by MTI 360.`
          : "Enquiry page hosted by MTI 360."
      }
    >
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8 tablet:px-6 desktop:py-12">
        {props.kind === "ok" ? (
          <>
            <header className="flex flex-col gap-2">
              <p className="text-body-sm font-semibold text-accent-maritime">
                {institute}
              </p>
              <h1 className="text-page-title text-text-primary">
                Ask about a course
              </h1>
              <p className="text-body text-text-secondary">
                Tell us what you would like to know about our maritime courses.
                A counsellor will contact you.
              </p>
            </header>
            <section
              aria-label="Enquiry form"
              className="rounded-lg border border-border-subtle bg-surface-primary p-4 tablet:p-6"
            >
              <EnquiryForm form={props.form} />
            </section>
          </>
        ) : (
          <ErrorState
            titleAs="h1"
            title="The enquiry page couldn't be loaded"
            description="Please try again in a few minutes."
            reference={props.reference ?? undefined}
          />
        )}
      </div>
    </PublicSiteShell>
  );
}
