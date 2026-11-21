import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
} from "@/design-system/components";
import { DetailTemplate } from "@/design-system/templates/DetailTemplate";
import { AllocationPanel } from "@/features/batches/AllocationPanel";
import { BatchActions } from "@/features/batches/BatchActions";
import { BatchHistory } from "@/features/batches/BatchHistory";
import {
  BATCH_READ,
  BATCHES_PATH,
  batchPath,
  STATUS_LABEL,
  STATUS_TONE,
} from "@/features/batches/labels";
import { SeatMeter } from "@/features/batches/SeatMeter";
import { coursePath } from "@/features/courses/labels";
import { formatDate } from "@/features/shared/format";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import { RecordLink } from "@/features/shared/RecordLink";
import type {
  AllocationWire,
  BatchActivityWire,
  BatchWire,
} from "@/lib/api/batches";
import { tenantApiRead } from "@/lib/api/server-read";
import {
  requireRecordId,
  settle,
  tenantPageAccess,
} from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { PageContainer, ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";
import type { ReactNode } from "react";

// ACA-06 Batch detail, /app/academics/batches/[batchId] (Phase 02-6). A batch
// of another institute or campus, or a malformed ID, is RESOURCE-02 (the API
// answers 404 for all of them). Summary and seats; allocated students and the
// allocation history (allocate, transfer, withdraw with batch.allocate); the
// batch history. Actions are UX only: the API decides.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Batch · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ batchId: string }> };

function Term({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 tablet:flex-row tablet:gap-6">
      <dt className="text-body-sm text-text-secondary tablet:w-32 tablet:shrink-0">
        {term}
      </dt>
      <dd className="min-w-0 text-body-sm break-words text-text-primary">
        {children}
      </dd>
    </div>
  );
}

export default async function BatchDetailPage({ params }: Props) {
  const id = requireRecordId((await params).batchId);
  const path = batchPath(id);
  const { session, allowed } = await tenantPageAccess(path, BATCH_READ);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const [read, activeRead, endedRead, historyRead] = await Promise.all([
    tenantApiRead<BatchWire>(`/batches/${id}`),
    tenantApiRead<AllocationWire[]>(
      `/batches/${id}/allocations?status=ACTIVE&limit=100`,
    ),
    tenantApiRead<AllocationWire[]>(
      `/batches/${id}/allocations?status=ENDED&limit=100`,
    ),
    tenantApiRead<BatchActivityWire[]>(`/batches/${id}/activity?limit=50`),
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
              title="This batch couldn't be loaded"
              reference={result.reference}
            />
          </PageContainer>
        )}
      </>
    );
  }
  const batch = result.data;
  const allocationsLoaded = activeRead.kind === "ok" && endedRead.kind === "ok";
  const activeTotal =
    activeRead.kind === "ok" ? (activeRead.page?.total ?? 0) : 0;
  return (
    <>
      <SessionSync session={session} />
      <DetailTemplate
        title={batch.name}
        description={`${batch.code} · ${batch.course.code} · ${batch.campus.name}`}
        breadcrumbs={[
          { label: "Academics" },
          { label: "Batches", href: BATCHES_PATH },
          { label: batch.code },
        ]}
        status={
          <Badge tone={STATUS_TONE[batch.status]}>
            {STATUS_LABEL[batch.status]}
          </Badge>
        }
        actions={<BatchActions batch={batch} />}
        asideLabel="Batch summary"
        main={
          allocationsLoaded ? (
            <>
              <AllocationPanel
                batch={batch}
                allocations={[
                  ...(activeRead.kind === "ok" ? activeRead.data : []),
                  ...(endedRead.kind === "ok" ? endedRead.data : []),
                ]}
              />
              {activeTotal > 100 && (
                <p className="text-caption text-text-secondary">
                  {`Showing the first 100 of ${activeTotal} allocated students.`}
                </p>
              )}
            </>
          ) : (
            <ReadErrorState
              title="Students couldn't be loaded"
              reference={null}
            />
          )
        }
        aside={
          <>
            <Card as="section">
              <CardHeader title="Summary" titleAs="h2" />
              <CardBody>
                <dl className="flex flex-col gap-4">
                  <Term term="Seats">
                    <SeatMeter
                      capacity={batch.capacity}
                      allocated={batch.allocated_count}
                    />
                  </Term>
                  <Term term="Available">{batch.available_seats}</Term>
                  <Term term="Course">
                    <RecordLink href={coursePath(batch.course.id)}>
                      {`${batch.course.code} · ${batch.course.name}`}
                    </RecordLink>
                  </Term>
                  <Term term="Campus">{batch.campus.name}</Term>
                  <Term term="Intake">{batch.intake_label ?? "Not set"}</Term>
                  <Term term="Dates">
                    {`${formatDate(batch.start_date)} – ${formatDate(batch.end_date)}`}
                  </Term>
                  <Term term="Status">
                    {STATUS_LABEL[batch.status]}
                    {batch.status_reason ? ` · ${batch.status_reason}` : ""}
                  </Term>
                </dl>
              </CardBody>
            </Card>
            <Card as="section">
              <CardHeader title="History" titleAs="h2" />
              <CardBody>
                {historyRead.kind !== "ok" ? (
                  <ReadErrorState
                    title="History couldn't be loaded"
                    reference={null}
                  />
                ) : historyRead.data.length === 0 ? (
                  <EmptyState
                    title="No history yet"
                    description="Changes to this batch appear here."
                  />
                ) : (
                  <BatchHistory entries={historyRead.data} />
                )}
              </CardBody>
            </Card>
          </>
        }
      />
    </>
  );
}
