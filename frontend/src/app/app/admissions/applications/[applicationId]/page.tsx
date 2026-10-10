import {
  Alert,
  Badge,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
} from "@/design-system/components";
import { DetailTemplate } from "@/design-system/templates/DetailTemplate";
import { ApplicationActions } from "@/features/applications/ApplicationActions";
import { ApplicationActivity } from "@/features/applications/ApplicationActivity";
import {
  APPLICATION_READ,
  APPLICATIONS_PATH,
  applicationPath,
  DOCUMENT_READ,
  REQUIREMENT_LABEL,
  STATUS_LABEL,
  STATUS_TONE,
  studentPath,
} from "@/features/applications/labels";
import { DocumentsPanel } from "@/features/documents/DocumentsPanel";
import {
  leadPath,
  STATUS_LABEL as LEAD_STATUS_LABEL,
} from "@/features/leads/labels";
import { formatDate, formatDateTime } from "@/features/shared/format";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import { RecordLink } from "@/features/shared/RecordLink";
import type {
  ApplicationActivityWire,
  ApplicationWire,
  DocumentWire,
} from "@/lib/api/admissions";
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
import type { ReactNode } from "react";

// ADM-06 Application detail, /app/admissions/applications/[id] (Phase 02-2;
// ADR-0021 §14) with ADM-08 review, ADM-09 documents and ADM-10 admission as
// its panels and dialogs (no separate screens, CLAUDE.md §59). The
// application, its documents (document.read) and its history are read in
// parallel on the server. Another institute's or campus's application is
// RESOURCE-02. The applicant's name is never put in the page title or URL.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Application · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ applicationId: string }> };

function Term({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 tablet:flex-row tablet:gap-6">
      <dt className="text-body-sm text-text-secondary tablet:w-44 tablet:shrink-0">
        {term}
      </dt>
      <dd className="min-w-0 text-body-sm break-words whitespace-pre-wrap text-text-primary">
        {children}
      </dd>
    </div>
  );
}

const given = (value: string | null) => value ?? "Not given";

function Applicant({ application: a }: { application: ApplicationWire }) {
  return (
    <Card as="section">
      <CardHeader title="Applicant" titleAs="h2" />
      <CardBody>
        <dl className="flex flex-col gap-4">
          <Term term="Name">{a.full_name}</Term>
          <Term term="Date of birth">
            {a.date_of_birth ? formatDate(a.date_of_birth) : "Not given"}
          </Term>
          <Term term="Mobile">{given(a.mobile)}</Term>
          <Term term="Email">{given(a.email)}</Term>
          <Term term="Address">
            {[a.address, a.city, a.state, a.postal_code]
              .filter(Boolean)
              .join(", ") || "Not given"}
          </Term>
          <Term term="Highest qualification">
            {given(a.highest_qualification)}
          </Term>
          <Term term="Education details">{given(a.education_details)}</Term>
          <Term term="INDoS number">{given(a.indos_number)}</Term>
          <Term term="CDC number">{given(a.cdc_number)}</Term>
          <Term term="Eligibility notes">{given(a.eligibility_notes)}</Term>
          <Term term="Declaration">
            {a.declared_at
              ? `Confirmed${a.declared_by ? ` by ${a.declared_by.display_name}` : ""} on ${formatDate(a.declared_at)}`
              : "Not confirmed yet"}
          </Term>
        </dl>
      </CardBody>
    </Card>
  );
}

function Progress({ application: a }: { application: ApplicationWire }) {
  return (
    <Card as="section">
      <CardHeader title="Progress" titleAs="h2" />
      <CardBody>
        <dl className="flex flex-col gap-4">
          <Term term="Status">
            <span className="flex flex-col gap-1">
              <Badge tone={STATUS_TONE[a.status]}>
                {STATUS_LABEL[a.status]}
              </Badge>
              <span className="text-caption text-text-secondary">
                {`Since ${formatDateTime(a.status_changed_at)}`}
              </span>
            </span>
          </Term>
          {a.status_reason && <Term term="Reason">{a.status_reason}</Term>}
          <Term term="Course">
            <span className="flex flex-wrap items-center gap-2">
              {`${a.course.code} · ${a.course.name}`}
              {a.course.status !== "ACTIVE" && (
                <Badge tone="warning">
                  {a.course.status === "ARCHIVED" ? "Archived" : "Draft"}
                </Badge>
              )}
            </span>
          </Term>
          <Term term="Campus">{a.campus.name}</Term>
          <Term term="Owner">{a.owner?.display_name ?? "Not set"}</Term>
          {a.lead && (
            <Term term="Lead">
              <span className="flex flex-col gap-1">
                <RecordLink href={leadPath(a.lead.id)}>
                  {a.lead.full_name}
                </RecordLink>
                <span className="text-caption text-text-secondary">
                  {LEAD_STATUS_LABEL[a.lead.status]}
                </span>
              </span>
            </Term>
          )}
          <Term term="Documents">
            {a.documents.total === 0
              ? "None uploaded"
              : `${a.documents.verified} of ${a.documents.total} verified`}
          </Term>
          {a.submitted_at && (
            <Term term="Submitted">{formatDateTime(a.submitted_at)}</Term>
          )}
          {a.reviewed_by && a.reviewed_at && (
            <Term term="Last decision">
              {`${a.reviewed_by.display_name}, ${formatDateTime(a.reviewed_at)}`}
            </Term>
          )}
        </dl>
      </CardBody>
    </Card>
  );
}

function Admission({ application: a }: { application: ApplicationWire }) {
  const admission = a.admission;
  if (!admission) return null;
  return (
    <Card as="section">
      <CardHeader title="Admission" titleAs="h2" />
      <CardBody>
        <dl className="flex flex-col gap-4">
          <Term term="Admission number">{admission.admission_number}</Term>
          <Term term="Student">
            {admission.student_visible ? (
              <RecordLink href={studentPath(admission.student_id)}>
                {admission.student_number}
              </RecordLink>
            ) : (
              admission.student_number
            )}
          </Term>
        </dl>
      </CardBody>
    </Card>
  );
}

function NextStep({ application: a }: { application: ApplicationWire }) {
  if (!a.editable || a.missing_for_submit.length === 0) return null;
  return (
    <Alert tone="warning" title="Before this application can be submitted">
      <ul className="list-disc pl-5">
        {a.missing_for_submit.map((item) => (
          <li key={item}>{REQUIREMENT_LABEL[item]}</li>
        ))}
      </ul>
    </Alert>
  );
}

export default async function ApplicationDetailPage({ params }: Props) {
  const id = requireRecordId((await params).applicationId);
  const path = applicationPath(id);
  const { session, allowed } = await tenantPageAccess(path, APPLICATION_READ);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const [read, documentsRead, activityRead] = await Promise.all([
    tenantApiRead<ApplicationWire>(`/applications/${id}`),
    can(session.permissions, DOCUMENT_READ)
      ? tenantApiRead<{ items: DocumentWire[] }>(
          `/applications/${id}/documents`,
        )
      : null,
    tenantApiRead<ApplicationActivityWire[]>(
      `/applications/${id}/activity?limit=50`,
    ),
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
      <DetailTemplate
        title={application.full_name}
        description={`Application ${application.number} · ${application.course.code} · ${application.campus.name}`}
        breadcrumbs={[
          { label: "Admissions" },
          { label: "Applications", href: APPLICATIONS_PATH },
          { label: application.number },
        ]}
        status={
          <Badge tone={STATUS_TONE[application.status]}>
            {STATUS_LABEL[application.status]}
          </Badge>
        }
        actions={<ApplicationActions application={application} />}
        asideLabel="Application progress"
        main={
          <>
            <NextStep application={application} />
            <Applicant application={application} />
            {documentsRead === null ? null : documentsRead.kind === "ok" ? (
              <DocumentsPanel
                applicationId={application.id}
                status={application.status}
                documents={documentsRead.data.items}
              />
            ) : (
              <ReadErrorState
                title="Documents couldn't be loaded"
                reference={null}
              />
            )}
          </>
        }
        aside={
          <>
            <Progress application={application} />
            <Admission application={application} />
          </>
        }
      >
        <Card as="section">
          <CardHeader title="History" titleAs="h2" />
          <CardBody>
            {activityRead.kind === "ok" ? (
              activityRead.data.length > 0 ? (
                <ApplicationActivity activities={activityRead.data} />
              ) : (
                <EmptyState
                  title="No history yet"
                  description="Changes, decisions and documents are recorded here."
                />
              )
            ) : (
              <ReadErrorState
                title="History couldn't be loaded"
                reference={null}
              />
            )}
          </CardBody>
        </Card>
      </DetailTemplate>
    </>
  );
}
