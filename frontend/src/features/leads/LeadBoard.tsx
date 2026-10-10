"use client";

import { useState } from "react";

import { Badge, Card, Select } from "@/design-system/components";
import { cx } from "@/design-system/lib/cx";
import type { LeadListItemWire, LeadStatus } from "@/lib/api/admissions";

import { RecordLink } from "../shared/RecordLink";

import { LEADS_PATH, leadPath, STATUS_LABEL } from "./labels";
import { LeadItemMenu } from "./LeadItemMenu";
import { NextFollowUp } from "./LeadTable";

// ADM-02 Lead pipeline (Phase 02-1; blueprint §22): the board VIEW of the
// Leads route — one column per open status with its total, built from the
// list API (one server read per column). A card moves only through its menu
// ("Move to…" → the same dialog and endpoint as the detail page); the board
// changes after the server answers (no optimistic move, no drag-and-drop).
// Tablet and up: columns side by side with horizontal scroll. Mobile: one
// column at a time, chosen with a status selector. Closed statuses are not
// columns; the list's status filter reaches them.

export type BoardColumn = {
  status: LeadStatus;
  leads: LeadListItemWire[];
  total: number;
};

function LeadCard({ lead }: { lead: LeadListItemWire }) {
  return (
    <Card as="article" padding="none">
      <div className="flex flex-col gap-2 p-3">
        <div className="flex items-start justify-between gap-2">
          <h3 className="min-w-0 text-body-sm">
            <RecordLink href={leadPath(lead.id)}>{lead.full_name}</RecordLink>
          </h3>
          <LeadItemMenu lead={lead} />
        </div>
        <dl className="flex flex-col gap-1 text-caption">
          <div className="flex gap-2">
            <dt className="shrink-0 text-text-secondary">Course</dt>
            <dd className="min-w-0 truncate text-text-primary">
              {lead.interested_course?.code ?? "—"}
            </dd>
          </div>
          <div className="flex gap-2">
            <dt className="shrink-0 text-text-secondary">Owner</dt>
            <dd className="min-w-0 truncate text-text-primary">
              {lead.owner?.display_name ?? "Unassigned"}
            </dd>
          </div>
          <div className="flex gap-2">
            <dt className="shrink-0 text-text-secondary">Follow-up</dt>
            <dd className="min-w-0 text-text-primary">
              <NextFollowUp
                at={lead.next_follow_up_at}
                overdue={lead.overdue_follow_ups}
              />
            </dd>
          </div>
        </dl>
      </div>
    </Card>
  );
}

export function LeadBoard({ columns }: { columns: BoardColumn[] }) {
  const [mobileColumn, setMobileColumn] = useState<LeadStatus>(
    columns[0]?.status ?? "NEW",
  );
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="tablet:hidden">
        <Select
          label="Pipeline stage"
          options={columns.map((column) => ({
            id: column.status,
            label: `${STATUS_LABEL[column.status]} (${column.total})`,
          }))}
          value={mobileColumn}
          onChange={(value) => value && setMobileColumn(value as LeadStatus)}
        />
      </div>
      <div className="-mx-4 overflow-x-auto px-4 pb-2 tablet:mx-0 tablet:px-0">
        <div className="flex gap-4">
          {columns.map((column) => {
            const headingId = `board-${column.status}`;
            return (
              <section
                key={column.status}
                aria-labelledby={headingId}
                className={cx(
                  "w-full shrink-0 flex-col gap-3 rounded-lg border border-border-subtle bg-surface-secondary p-3 tablet:flex tablet:w-72",
                  column.status === mobileColumn ? "flex" : "hidden",
                )}
              >
                <h2
                  id={headingId}
                  className="flex items-center justify-between gap-2 text-body-sm font-semibold text-text-primary"
                >
                  <span>{STATUS_LABEL[column.status]}</span>
                  <Badge>{`${column.total} ${column.total === 1 ? "lead" : "leads"}`}</Badge>
                </h2>
                {column.leads.length === 0 ? (
                  <p className="text-body-sm text-text-secondary">
                    No leads at this stage.
                  </p>
                ) : (
                  <ul className="flex flex-col gap-3">
                    {column.leads.map((lead) => (
                      <li key={lead.id}>
                        <LeadCard lead={lead} />
                      </li>
                    ))}
                  </ul>
                )}
                {column.total > column.leads.length && (
                  <RecordLink
                    href={`${LEADS_PATH}?view=list&status=${column.status}`}
                  >
                    {`View all ${column.total} in the list`}
                  </RecordLink>
                )}
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
