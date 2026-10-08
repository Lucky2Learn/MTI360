"use client";

import Link from "next/link";

import {
  Button,
  FilterBar,
  Search,
  Select,
  Tab,
  TabList,
  TabPanel,
  Tabs,
  type DataTableEmptyState,
} from "@/design-system/components";
import { AddIcon } from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";
import type { CourseWire, LeadListItemWire } from "@/lib/api/admissions";
import type { PageMeta } from "@/lib/api/server-read";
import { PermissionGate } from "@/lib/authz/PermissionGate";
import { nextQuery, useListParams } from "@/lib/navigation/list-params";
import { useTenantSession } from "@/lib/session/SessionProvider";

import {
  LEAD_CREATE,
  LEADS_PATH,
  options,
  SOURCE_LABEL,
  STATUS_LABEL,
} from "./labels";
import { LeadBoard, type BoardColumn } from "./LeadBoard";
import { LeadTable } from "./LeadTable";
import { ALL_STATUSES, type LeadView } from "./query";

// GROW-08 Leads / ADM-02 Pipeline (Phase 02-1; blueprint §20-§23): one route,
// two views (List / Board) chosen with Tabs, the same filters for both. Quick
// filters are links to URL states; the FilterBar holds the rest (a Drawer on
// mobile). Filter values are IDs and enums; only the search box puts text
// in the URL.

const ANY = "any";

export function NewLeadButton() {
  return (
    <PermissionGate permission={LEAD_CREATE}>
      <Button href={`${LEADS_PATH}/new`} iconStart={AddIcon}>
        New lead
      </Button>
    </PermissionGate>
  );
}

/** The browser's offset east of UTC, for the "today" follow-up filter. */
function browserOffset(): string {
  return String(-new Date().getTimezoneOffset());
}

function QuickFilters() {
  const params = useListParams();
  const current = new URLSearchParams(params.query);
  const chips: { label: string; updates: Record<string, string | null> }[] = [
    { label: "My leads", updates: { owner: "me" } },
    { label: "Unassigned", updates: { owner: "unassigned" } },
    { label: "Overdue follow-ups", updates: { follow_up: "overdue" } },
    {
      label: "Follow-ups today",
      updates: { follow_up: "today", utc_offset: browserOffset() },
    },
  ];
  return (
    <nav aria-label="Quick filters">
      <ul className="flex flex-wrap gap-2">
        {chips.map((chip) => {
          const active = Object.entries(chip.updates).every(
            ([key, value]) =>
              key === "utc_offset" || current.get(key) === value,
          );
          const href = `${LEADS_PATH}?${nextQuery(
            current,
            active
              ? Object.fromEntries(
                  Object.keys(chip.updates).map((k) => [k, null]),
                )
              : chip.updates,
          )}`;
          return (
            <li key={chip.label}>
              <Link
                href={href}
                aria-current={active ? "true" : undefined}
                className={cx(
                  "inline-flex min-h-control-md items-center rounded-full border px-3 text-body-sm",
                  active
                    ? "border-brand-primary bg-surface-selected font-medium text-text-primary"
                    : "border-border-default bg-surface-primary text-text-secondary hover:bg-surface-hover",
                  focusRing,
                )}
              >
                {chip.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function LeadFilters({
  total,
  courses,
}: {
  total: string;
  courses: CourseWire[];
}) {
  const params = useListParams();
  const { session } = useTenantSession();
  const value = (key: string) => params.get(key) ?? ANY;
  const set = (key: string) => (next: string | null) =>
    params.set({
      [key]: next === ANY ? null : next,
      ...(key === "follow_up" && next === "today"
        ? { utc_offset: browserOffset() }
        : {}),
    });
  const activeCount = [
    "status",
    "owner",
    "campus",
    "course",
    "source",
    "follow_up",
  ].filter((key) => params.get(key)).length;

  return (
    <FilterBar
      label="Lead filters"
      search={
        <Search
          label="Search leads"
          isLabelHidden
          placeholder="Search by name, email or mobile"
          defaultValue={params.get("q") ?? ""}
          onSubmit={(text) => params.set({ q: text.trim() || null })}
          onClear={() => params.set({ q: null })}
        />
      }
      activeFilterCount={activeCount}
      resultCount={total}
      onClear={() =>
        params.set({
          status: null,
          owner: null,
          campus: null,
          course: null,
          source: null,
          follow_up: null,
          utc_offset: null,
        })
      }
      filters={
        <>
          <Select
            label="Status"
            options={[
              { id: ANY, label: "Open leads" },
              { id: ALL_STATUSES, label: "All statuses" },
              ...options(STATUS_LABEL),
            ]}
            value={value("status")}
            onChange={set("status")}
          />
          <Select
            label="Owner"
            options={[
              { id: ANY, label: "Anyone" },
              { id: "me", label: "Me" },
              { id: "unassigned", label: "Unassigned" },
            ]}
            value={value("owner")}
            onChange={set("owner")}
          />
          <Select
            label="Campus"
            options={[
              { id: ANY, label: "All my campuses" },
              { id: "none", label: "Institute-wide" },
              ...session.campusOptions.map((c) => ({
                id: c.id,
                label: c.name,
              })),
            ]}
            value={value("campus")}
            onChange={set("campus")}
          />
          <Select
            label="Course"
            options={[
              { id: ANY, label: "Any course" },
              ...courses.map((c) => ({
                id: c.id,
                label: `${c.code} · ${c.name}`,
              })),
            ]}
            value={value("course")}
            onChange={set("course")}
          />
          <Select
            label="Source"
            options={[
              { id: ANY, label: "Any source" },
              ...options(SOURCE_LABEL),
            ]}
            value={value("source")}
            onChange={set("source")}
          />
          <Select
            label="Follow-up"
            options={[
              { id: ANY, label: "Any" },
              { id: "overdue", label: "Overdue" },
              { id: "today", label: "Due today" },
              { id: "upcoming", label: "Upcoming" },
              { id: "none", label: "No open follow-up" },
            ]}
            value={value("follow_up")}
            onChange={set("follow_up")}
          />
        </>
      }
    />
  );
}

export type LeadsWorkspaceProps = {
  view: LeadView;
  courses: CourseWire[];
  list?: { leads: LeadListItemWire[]; page: PageMeta };
  board?: BoardColumn[];
};

export function LeadsWorkspace({
  view,
  courses,
  list,
  board,
}: LeadsWorkspaceProps) {
  const params = useListParams();
  const { can } = useTenantSession();
  const filtered = [
    "q",
    "status",
    "owner",
    "campus",
    "course",
    "source",
    "follow_up",
  ].some((key) => params.get(key));
  const total = list
    ? list.page.total
    : (board ?? []).reduce((sum, column) => sum + column.total, 0);
  const emptyState: DataTableEmptyState = filtered
    ? {
        title: "No leads match these filters",
        description: "Try another search term or clear the filters.",
      }
    : can(LEAD_CREATE)
      ? {
          title: "No leads yet",
          description: "Add your first enquiry to start the pipeline.",
          action: <NewLeadButton />,
        }
      : {
          title: "No leads yet",
          description: "Leads appear here once your team records enquiries.",
        };

  const content =
    view === "board" ? (
      <LeadBoard columns={board ?? []} />
    ) : (
      <LeadTable
        leads={list?.leads ?? []}
        page={list?.page ?? { limit: 25, offset: 0, total: 0 }}
        emptyState={emptyState}
      />
    );

  return (
    <Tabs
      selectedKey={view}
      onSelectionChange={(key) =>
        params.set({ view: key === "board" ? "board" : null })
      }
    >
      <div className="flex min-w-0 flex-col gap-4">
        <TabList aria-label="Lead views">
          <Tab id="list">List</Tab>
          <Tab id="board">Board</Tab>
        </TabList>
        <QuickFilters />
        <LeadFilters
          total={`${total} ${total === 1 ? "lead" : "leads"}`}
          courses={courses}
        />
        <TabPanel id="list">{view === "list" ? content : null}</TabPanel>
        <TabPanel id="board">{view === "board" ? content : null}</TabPanel>
      </div>
    </Tabs>
  );
}
