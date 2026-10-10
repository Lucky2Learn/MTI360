"use client";

import {
  Badge,
  DataTable,
  Pagination,
  type DataTableColumn,
  type DataTableEmptyState,
  type SortDescriptor,
} from "@/design-system/components";
import type { LeadListItemWire } from "@/lib/api/admissions";
import type { PageMeta } from "@/lib/api/server-read";
import { useListParams } from "@/lib/navigation/list-params";

import { formatDate, formatDateTime } from "../shared/format";
import { RecordLink } from "../shared/RecordLink";

import { leadPath, STATUS_LABEL, STATUS_TONE } from "./labels";
import { LeadItemMenu } from "./LeadItemMenu";

// GROW-08 Lead list (Phase 02-1; blueprint §21): one row per lead with its
// contact, course, campus, owner, status and next follow-up (overdue marked
// with text, not colour alone). Mobile shows each row as a card. Sort and page
// live in the URL.

const SORT_COLUMNS: Record<string, string> = {
  name: "full_name",
  created: "created_at",
  followUp: "next_follow_up_at",
};

function descriptor(sort: string | null): SortDescriptor {
  const value = sort ?? "-created_at";
  const field = value.replace(/^-/, "");
  const column =
    Object.entries(SORT_COLUMNS).find(([, api]) => api === field)?.[0] ??
    "created";
  return {
    columnId: column,
    direction: value.startsWith("-") ? "descending" : "ascending",
  };
}

export function NextFollowUp({
  at,
  overdue,
}: {
  at: string | null;
  overdue: number;
}) {
  if (!at) return <span className="text-text-secondary">None</span>;
  return (
    <span className="flex flex-wrap items-center gap-2">
      <span>{formatDateTime(at)}</span>
      {overdue > 0 && <Badge tone="error">Overdue</Badge>}
    </span>
  );
}

export function LeadTable({
  leads,
  page,
  emptyState,
}: {
  leads: LeadListItemWire[];
  page: PageMeta;
  emptyState: DataTableEmptyState;
}) {
  const params = useListParams();
  const columns: DataTableColumn<LeadListItemWire>[] = [
    {
      id: "name",
      header: "Name",
      isRowHeader: true,
      isSortable: true,
      cell: (lead) => (
        <RecordLink href={leadPath(lead.id)}>{lead.full_name}</RecordLink>
      ),
    },
    {
      id: "contact",
      header: "Contact",
      cell: (lead) => (
        <span className="flex flex-col break-all">
          {lead.mobile && <span>{lead.mobile}</span>}
          {lead.email && (
            <span className="text-text-secondary">{lead.email}</span>
          )}
        </span>
      ),
    },
    {
      id: "course",
      header: "Course",
      cell: (lead) => lead.interested_course?.code ?? "—",
    },
    {
      id: "campus",
      header: "Campus",
      visibleFrom: "tablet",
      cell: (lead) => lead.campus?.code ?? "Institute-wide",
    },
    {
      id: "owner",
      header: "Owner",
      cell: (lead) => lead.owner?.display_name ?? "Unassigned",
    },
    {
      id: "status",
      header: "Status",
      cell: (lead) => (
        <Badge tone={STATUS_TONE[lead.status]}>
          {STATUS_LABEL[lead.status]}
        </Badge>
      ),
    },
    {
      id: "followUp",
      header: "Next follow-up",
      isSortable: true,
      visibleFrom: "desktop",
      cell: (lead) => (
        <NextFollowUp
          at={lead.next_follow_up_at}
          overdue={lead.overdue_follow_ups}
        />
      ),
    },
    {
      id: "created",
      header: "Created",
      isSortable: true,
      visibleFrom: "desktop",
      cell: (lead) => formatDate(lead.created_at),
    },
  ];

  return (
    <DataTable
      label="Leads"
      columns={columns}
      rows={leads}
      getRowId={(lead) => lead.id}
      getRowLabel={(lead) => lead.full_name}
      mobileLayout="cards"
      rowActions={(lead) => <LeadItemMenu lead={lead} />}
      rowActionsLabel="Actions"
      sort={descriptor(params.get("sort"))}
      onSortChange={(sort) => {
        const api = sort ? SORT_COLUMNS[sort.columnId] : undefined;
        params.set({
          sort: api
            ? `${sort?.direction === "descending" ? "-" : ""}${api}`
            : null,
        });
      }}
      emptyState={emptyState}
      footer={
        page.total > page.limit ? (
          <Pagination
            label="Lead pages"
            itemLabel="leads"
            page={Math.floor(page.offset / page.limit) + 1}
            pageSize={page.limit}
            totalItems={page.total}
            onPageChange={(next) =>
              params.set(
                { offset: next > 1 ? String((next - 1) * page.limit) : null },
                { keepPage: true },
              )
            }
          />
        ) : undefined
      }
    />
  );
}
