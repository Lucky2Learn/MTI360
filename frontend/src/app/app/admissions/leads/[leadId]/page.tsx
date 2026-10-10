import { Badge, Card, CardBody, CardHeader } from "@/design-system/components";
import { DetailTemplate } from "@/design-system/templates/DetailTemplate";
import { APPLICATION_READ } from "@/features/applications/labels";
import { LeadApplications } from "@/features/applications/LeadApplications";
import { FollowUpsPanel } from "@/features/leads/FollowUpsPanel";
import {
  LEAD_READ,
  LEADS_PATH,
  leadPath,
  SOURCE_LABEL,
  STATUS_LABEL,
  STATUS_TONE,
} from "@/features/leads/labels";
import { LeadActivity } from "@/features/leads/LeadActivity";
import { LeadDetailActions } from "@/features/leads/LeadDetailActions";
import { NextFollowUp } from "@/features/leads/LeadTable";
import { formatDate, formatDateTime } from "@/features/shared/format";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import { RecordLink } from "@/features/shared/RecordLink";
import type {
  ActivityWire,
  ApplicationListItemWire,
  FollowUpWire,
  LeadWire,
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

// GROW-09 Lead detail (Lead 360), /app/admissions/leads/[leadId] (Phase 02-1;
// blueprint §21). The lead, its follow-ups and its latest activity are read
// in parallel on the server. A lead of another institute, or of a campus
// outside the member's campuses, is RESOURCE-02 (the API answers 404 for
// both). The name is never put in the page title or the URL.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Lead · Tenant Application · MTI 360",
};

const ACTIVITY_LIMIT = 50;

type Props = { params: Promise<{ leadId: string }> };

function Term({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 tablet:flex-row tablet:gap-6">
      <dt className="text-body-sm text-text-secondary tablet:w-40 tablet:shrink-0">
        {term}
      </dt>
      <dd className="min-w-0 text-body-sm break-words text-text-primary">
        {children}
      </dd>
    </div>
  );
}

function Enquiry({ lead }: { lead: LeadWire }) {
  const course = lead.interested_course;
  return (
    <Card as="section">
      <CardHeader title="Enquiry" titleAs="h2" />
      <CardBody>
        <dl className="flex flex-col gap-4">
          <Term term="Mobile">{lead.mobile ?? "Not given"}</Term>
          <Term term="Email">{lead.email ?? "Not given"}</Term>
          <Term term="Interested course">
            {course ? (
              <span className="flex flex-wrap items-center gap-2">
                {`${course.code} · ${course.name}`}
                {course.status !== "ACTIVE" && (
                  <Badge tone="warning">
                    {course.status === "ARCHIVED" ? "Archived" : "Draft"}
                  </Badge>
                )}
              </span>
            ) : (
              "Not chosen yet"
            )}
          </Term>
          <Term term="Source">{SOURCE_LABEL[lead.source]}</Term>
          <Term term="Date of birth">
            {lead.date_of_birth ? formatDate(lead.date_of_birth) : "Not given"}
          </Term>
          <Term term="City">{lead.city ?? "Not given"}</Term>
          <Term term="Qualification">
            {lead.highest_qualification ?? "Not given"}
          </Term>
          <Term term="Created">
            {`${formatDateTime(lead.created_at)}${lead.created_by ? ` by ${lead.created_by.display_name}` : ""}`}
          </Term>
        </dl>
      </CardBody>
    </Card>
  );
}

function Pipeline({ lead }: { lead: LeadWire }) {
  return (
    <Card as="section">
      <CardHeader title="Pipeline" titleAs="h2" />
      <CardBody>
        <dl className="flex flex-col gap-4">
          <Term term="Status">
            <span className="flex flex-col gap-1">
              <Badge tone={STATUS_TONE[lead.status]}>
                {STATUS_LABEL[lead.status]}
              </Badge>
              <span className="text-caption text-text-secondary">
                {`Since ${formatDateTime(lead.status_changed_at)}`}
              </span>
            </span>
          </Term>
          {lead.status_reason && (
            <Term term="Reason">{lead.status_reason}</Term>
          )}
          {lead.duplicate_of && (
            <Term term="Duplicate of">
              <RecordLink href={leadPath(lead.duplicate_of.id)}>
                {lead.duplicate_of.full_name}
              </RecordLink>
            </Term>
          )}
          <Term term="Owner">
            {lead.owner
              ? `${lead.owner.display_name}${lead.owner.active ? "" : " (inactive)"}`
              : "Unassigned"}
          </Term>
          <Term term="Campus">{lead.campus?.name ?? "Institute-wide"}</Term>
          <Term term="Next follow-up">
            <NextFollowUp
              at={lead.next_follow_up_at}
              overdue={lead.overdue_follow_ups}
            />
          </Term>
        </dl>
      </CardBody>
    </Card>
  );
}

export default async function LeadDetailPage({ params }: Props) {
  const id = requireRecordId((await params).leadId);
  const path = leadPath(id);
  const { session, allowed } = await tenantPageAccess(path, LEAD_READ);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const [leadRead, followUpsRead, activityRead, applicationsRead] =
    await Promise.all([
      tenantApiRead<LeadWire>(`/leads/${id}`),
      tenantApiRead<{ items: FollowUpWire[] }>(`/leads/${id}/follow-ups`),
      tenantApiRead<ActivityWire[]>(
        `/leads/${id}/activity?limit=${ACTIVITY_LIMIT}`,
      ),
      // Phase 02-2: the lead's applications (application.read only).
      can(session.permissions, APPLICATION_READ)
        ? tenantApiRead<ApplicationListItemWire[]>(
            `/applications?lead=${id}&limit=20&sort=-created_at`,
          )
        : null,
    ]);
  const lead = settle(leadRead, path);
  if (lead.kind !== "ok") {
    return (
      <>
        <SessionSync session={session} />
        {lead.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <PageContainer>
            <ReadErrorState
              title="This lead couldn't be loaded"
              reference={lead.reference}
            />
          </PageContainer>
        )}
      </>
    );
  }
  const data = lead.data;
  const followUps =
    followUpsRead.kind === "ok" ? followUpsRead.data.items : null;
  const activity = activityRead.kind === "ok" ? activityRead : null;

  return (
    <>
      <SessionSync session={session} />
      <DetailTemplate
        title={data.full_name}
        description={`${SOURCE_LABEL[data.source]} enquiry${data.interested_course ? ` · ${data.interested_course.code}` : ""}`}
        breadcrumbs={[
          { label: "Admissions" },
          { label: "Leads", href: LEADS_PATH },
          { label: "Lead" },
        ]}
        status={
          <Badge tone={STATUS_TONE[data.status]}>
            {STATUS_LABEL[data.status]}
          </Badge>
        }
        actions={<LeadDetailActions lead={data} />}
        asideLabel="Lead pipeline and follow-ups"
        main={<Enquiry lead={data} />}
        aside={
          <>
            <Pipeline lead={data} />
            {applicationsRead?.kind === "ok" && (
              <LeadApplications applications={applicationsRead.data} />
            )}
            {followUps ? (
              <FollowUpsPanel
                leadId={data.id}
                campusId={data.campus?.id ?? null}
                followUps={followUps}
              />
            ) : (
              <ReadErrorState
                title="Follow-ups couldn't be loaded"
                reference={null}
              />
            )}
          </>
        }
      >
        {activity ? (
          <LeadActivity
            leadId={data.id}
            activities={activity.data}
            total={activity.page?.total ?? activity.data.length}
          />
        ) : (
          <ReadErrorState
            title="Activity couldn't be loaded"
            reference={null}
          />
        )}
      </DetailTemplate>
    </>
  );
}
