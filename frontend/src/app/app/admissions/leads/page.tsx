import { DataListTemplate } from "@/design-system/templates/DataListTemplate";
import type { SearchParams } from "@/features/courses/query";
import {
  COURSE_READ,
  LEAD_READ,
  LEADS_PATH,
  PIPELINE,
} from "@/features/leads/labels";
import type { BoardColumn } from "@/features/leads/LeadBoard";
import {
  LeadsWorkspace,
  NewLeadButton,
  type LeadsWorkspaceProps,
} from "@/features/leads/LeadsWorkspace";
import {
  boardColumnQuery,
  leadListQuery,
  viewOf,
  type LeadView,
} from "@/features/leads/query";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { CourseWire, LeadListItemWire } from "@/lib/api/admissions";
import { tenantApiRead } from "@/lib/api/server-read";
import { can } from "@/lib/authz/requirements";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// GROW-08 Leads (list) and ADM-02 Lead pipeline (board),
// /app/admissions/leads[?view=board] (Phase 02-1; blueprint §20-§23). Gate:
// ready session → lead.read → server reads with the tenant cookie only: the
// list page, or one read per open status for the board. The API applies the
// campus rule to every read: a campus-restricted member sees the institute
// pool and their campuses only.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Leads · Tenant Application · MTI 360",
};

const BREADCRUMBS = [{ label: "Admissions" }, { label: "Leads" }];

type Outcome =
  | { kind: "ok"; data: Pick<LeadsWorkspaceProps, "list" | "board"> }
  | { kind: "denied" }
  | { kind: "error"; reference: string | null };

async function readView(
  params: SearchParams,
  view: LeadView,
): Promise<Outcome> {
  if (view === "list") {
    const read = settle(
      await tenantApiRead<LeadListItemWire[]>(
        `/leads?${leadListQuery(params)}`,
      ),
      LEADS_PATH,
    );
    if (read.kind !== "ok") return read;
    const page = read.page ?? { limit: 25, offset: 0, total: read.data.length };
    return { kind: "ok", data: { list: { leads: read.data, page } } };
  }
  const reads = await Promise.all(
    PIPELINE.map((status) =>
      tenantApiRead<LeadListItemWire[]>(
        `/leads?${boardColumnQuery(params, status)}`,
      ),
    ),
  );
  const board: BoardColumn[] = [];
  for (const [index, read] of reads.entries()) {
    const settled = settle(read, LEADS_PATH);
    if (settled.kind !== "ok") return settled;
    board.push({
      status: PIPELINE[index] ?? "NEW",
      leads: settled.data,
      total: settled.page?.total ?? settled.data.length,
    });
  }
  return { kind: "ok", data: { board } };
}

export default async function LeadsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { session, allowed } = await tenantPageAccess(LEADS_PATH, LEAD_READ);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const params = await searchParams;
  const view = viewOf(params);
  const [outcome, courses] = await Promise.all([
    readView(params, view),
    can(session.permissions, COURSE_READ)
      ? tenantApiRead<CourseWire[]>("/courses?limit=100&sort=name")
      : null,
  ]);

  return (
    <>
      <SessionSync session={session} />
      <DataListTemplate
        title="Leads"
        description="Enquiries from every source, from first contact to ready to apply."
        breadcrumbs={BREADCRUMBS}
        actions={<NewLeadButton />}
      >
        {outcome.kind === "ok" ? (
          <LeadsWorkspace
            view={view}
            courses={courses?.kind === "ok" ? courses.data : []}
            {...outcome.data}
          />
        ) : outcome.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <ReadErrorState
            title="Leads couldn't be loaded"
            reference={outcome.reference}
          />
        )}
      </DataListTemplate>
    </>
  );
}
