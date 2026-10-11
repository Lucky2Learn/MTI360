"use client";

import {
  Badge,
  Button,
  DataTable,
  FilterBar,
  Pagination,
  Search,
  Select,
  type DataTableColumn,
} from "@/design-system/components";
import { AddIcon } from "@/design-system/icons";
import type { FeeStructureWire } from "@/lib/api/finance";
import type { PageMeta } from "@/lib/api/server-read";
import { PermissionGate } from "@/lib/authz/PermissionGate";
import { useListParams } from "@/lib/navigation/list-params";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { RecordLink } from "../shared/RecordLink";

import {
  FEE_STRUCTURE_MANAGE,
  STRUCTURE_STATUS_LABEL,
  STRUCTURE_STATUS_TONE,
  STRUCTURES_PATH,
  structurePath,
} from "./labels";
import { formatPaise } from "./money";

// FIN-02 Fee structures (Phase 02-5; readiness plan §4): the institute's fee
// heads per course, for every member with fee_structure.read (structures are
// institute-wide, like courses). Search and status live in the URL; the
// server renders the page. "New fee structure" needs fee_structure.manage
// (UX only; the API refuses the request anyway).

const ANY = "any";

export function NewStructureButton() {
  return (
    <PermissionGate permission={FEE_STRUCTURE_MANAGE}>
      <Button href={`${STRUCTURES_PATH}/new`} iconStart={AddIcon}>
        New fee structure
      </Button>
    </PermissionGate>
  );
}

export function FeeStructureList({
  structures,
  page,
}: {
  structures: FeeStructureWire[];
  page: PageMeta;
}) {
  const params = useListParams();
  const { can } = useTenantSession();
  const q = params.get("q") ?? "";
  const status = params.get("status");
  const filtered = Boolean(q || status);

  const columns: DataTableColumn<FeeStructureWire>[] = [
    {
      id: "name",
      header: "Fee structure",
      isRowHeader: true,
      cell: (structure) => (
        <RecordLink href={structurePath(structure.id)}>
          {structure.name}
        </RecordLink>
      ),
    },
    {
      id: "course",
      header: "Course",
      cell: (structure) =>
        `${structure.course.code} · ${structure.course.name}`,
    },
    {
      id: "heads",
      header: "Fee heads",
      visibleFrom: "tablet",
      cell: (structure) => String(structure.items.length),
    },
    {
      id: "total",
      header: "Total",
      align: "end",
      cell: (structure) => (
        <span className="tabular-nums">
          {formatPaise(structure.total_minor)}
        </span>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: (structure) => (
        <Badge tone={STRUCTURE_STATUS_TONE[structure.status]}>
          {STRUCTURE_STATUS_LABEL[structure.status]}
        </Badge>
      ),
    },
  ];

  const emptyState = filtered
    ? {
        title: "No fee structures match these filters",
        description: "Try another search term or clear the filters.",
        action: (
          <Button
            variant="secondary"
            onPress={() => params.set({ q: null, status: null })}
          >
            Clear filters
          </Button>
        ),
      }
    : can(FEE_STRUCTURE_MANAGE)
      ? {
          title: "No fee structures yet",
          description:
            "Set the fee heads of a course, such as tuition, hostel and uniform, so fee invoices can be issued to admitted students.",
          action: <NewStructureButton />,
        }
      : {
          title: "No fee structures yet",
          description:
            "Fee structures appear here once your finance team adds them.",
        };

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <FilterBar
        label="Fee structure filters"
        search={
          <Search
            label="Search fee structures"
            isLabelHidden
            placeholder="Search by name or course"
            defaultValue={q}
            onSubmit={(value) => params.set({ q: value.trim() || null })}
            onClear={() => params.set({ q: null })}
          />
        }
        activeFilterCount={status ? 1 : 0}
        resultCount={`${page.total} ${page.total === 1 ? "fee structure" : "fee structures"}`}
        onClear={() => params.set({ status: null })}
        filters={
          <Select
            label="Status"
            options={[
              { id: ANY, label: "Any status" },
              { id: "ACTIVE", label: "Active" },
              { id: "DRAFT", label: "Draft" },
              { id: "ARCHIVED", label: "Archived" },
            ]}
            value={status ?? ANY}
            onChange={(value) =>
              params.set({ status: value === ANY ? null : value })
            }
          />
        }
      />
      <DataTable
        label="Fee structures"
        columns={columns}
        rows={structures}
        getRowId={(structure) => structure.id}
        getRowLabel={(structure) => structure.name}
        mobileLayout="cards"
        emptyState={emptyState}
        footer={
          page.total > page.limit ? (
            <Pagination
              label="Fee structure pages"
              itemLabel="fee structures"
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
    </div>
  );
}
