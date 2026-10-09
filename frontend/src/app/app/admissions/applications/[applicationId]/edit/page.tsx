import { Alert, Badge, Button } from "@/design-system/components";
import { WizardTemplate } from "@/design-system/templates/WizardTemplate";
import {
  ApplicationWizardStep,
  stepComplete,
  WIZARD_STEPS,
  type WizardStepId,
} from "@/features/applications/ApplicationWizard";
import {
  APPLICATION_UPDATE,
  APPLICATIONS_PATH,
  applicationPath,
  applicationStepPath,
  STATUS_LABEL,
  STATUS_TONE,
} from "@/features/applications/labels";
import { first, type SearchParams } from "@/features/courses/query";
import { COURSE_READ } from "@/features/leads/labels";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { ApplicationWire, CourseWire } from "@/lib/api/admissions";
import { tenantApiRead } from "@/lib/api/server-read";
import { can } from "@/lib/authz/requirements";
import {
  requireRecordId,
  settle,
  tenantPageAccess,
} from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { PageContainer, ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// ADM-07 application wizard, /app/admissions/applications/[id]/edit?step=…
// (Phase 02-2; ADR-0021 §3, §14). application.update. Each step is its own URL
// so a draft is resumed where it was left. A submitted application is not
// edited here: the page says so and links back to the application.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Application · Tenant Application · MTI 360",
};

type Props = {
  params: Promise<{ applicationId: string }>;
  searchParams: Promise<SearchParams>;
};

export default async function EditApplicationPage({
  params,
  searchParams,
}: Props) {
  const id = requireRecordId((await params).applicationId);
  const path = `${applicationPath(id)}/edit`;
  const { session, allowed } = await tenantPageAccess(path, APPLICATION_UPDATE);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const requested = first((await searchParams).step);
  const step: WizardStepId = WIZARD_STEPS.some((s) => s.id === requested)
    ? (requested as WizardStepId)
    : "personal";
  const [read, courses] = await Promise.all([
    tenantApiRead<ApplicationWire>(`/applications/${id}`),
    step === "course" && can(session.permissions, COURSE_READ)
      ? tenantApiRead<CourseWire[]>(
          "/courses?status=ACTIVE&limit=100&sort=name",
        )
      : null,
  ]);
  const result = settle(read, path);
  if (result.kind !== "ok") {
    return (
      <>
        <SessionSync session={session} />
        {result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <PageContainer>
            <ReadErrorState
              title="This application couldn't be loaded"
              reference={result.reference}
            />
          </PageContainer>
        )}
      </>
    );
  }
  const application = result.data;
  return (
    <>
      <SessionSync session={session} />
      <WizardTemplate
        title={
          application.editable
            ? `Application ${application.number}`
            : application.number
        }
        description={`${application.course.code} · ${application.campus.name}`}
        breadcrumbs={[
          { label: "Admissions" },
          { label: "Applications", href: APPLICATIONS_PATH },
          { label: application.number, href: applicationPath(application.id) },
          { label: "Edit" },
        ]}
        status={
          <Badge tone={STATUS_TONE[application.status]}>
            {STATUS_LABEL[application.status]}
          </Badge>
        }
        steps={WIZARD_STEPS.map((s) => ({
          id: s.id,
          label: s.label,
          href: applicationStepPath(application.id, s.id),
          complete: stepComplete(s.id, application),
        }))}
        currentStep={step}
        stepsLabel="Application steps"
      >
        {application.editable ? (
          <>
            {application.status === "CORRECTION_REQUIRED" &&
              application.status_reason && (
                <Alert tone="warning" title="Correction requested">
                  {application.status_reason}
                </Alert>
              )}
            <ApplicationWizardStep
              key={`${step}-${application.version}`}
              application={application}
              step={step}
              courses={courses?.kind === "ok" ? courses.data : []}
            />
          </>
        ) : (
          <Alert tone="info" title="This application has been submitted">
            <span className="flex flex-col gap-3">
              Its details can no longer be changed here. A reviewer can request
              a correction.
              <span>
                <Button
                  variant="secondary"
                  href={applicationPath(application.id)}
                >
                  Back to the application
                </Button>
              </span>
            </span>
          </Alert>
        )}
      </WizardTemplate>
    </>
  );
}
