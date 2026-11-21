"use client";

import { DataTable, type DataTableColumn } from "@/design-system/components";
import type { TenantCampusWire } from "@/lib/api/tenant-admin";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { formatDate } from "../shared/format";
import { RecordLink } from "../shared/RecordLink";

import { AddCampusButton } from "./CampusDialogs";
import { CAMPUS_CREATE, campusPath } from "./labels";

// ADMIN-03 Campuses (02-C; GET /campuses, campus.read): the caller's own
// campuses, by name, as the API returns them (all of them with all-campus
// access, D-B1). The API returns every campus at once, so there is no
// paging or filtering.

export function CampusList({ campuses }: { campuses: TenantCampusWire[] }) {
  const { can } = useTenantSession();

  const columns: DataTableColumn<TenantCampusWire>[] = [
    {
      id: "name",
      header: "Campus",
      isRowHeader: true,
      cell: (campus) => (
        <RecordLink href={campusPath(campus.id)}>{campus.name}</RecordLink>
      ),
    },
    {
      id: "code",
      header: "Code",
      cell: (campus) => <span className="break-all">{campus.code}</span>,
    },
    {
      id: "created",
      header: "Added",
      visibleFrom: "tablet",
      cell: (campus) => formatDate(campus.created_at),
    },
    {
      id: "updated",
      header: "Last changed",
      visibleFrom: "desktop",
      cell: (campus) => formatDate(campus.updated_at),
    },
  ];

  return (
    <DataTable
      label="Campuses"
      columns={columns}
      rows={campuses}
      getRowId={(campus) => campus.id}
      getRowLabel={(campus) => campus.name}
      mobileLayout="cards"
      emptyState={
        can(CAMPUS_CREATE)
          ? {
              title: "No campuses yet",
              description:
                "Add your institute's campuses so staff, leads and batches can be organised by location.",
              action: <AddCampusButton />,
            }
          : {
              title: "No campuses to show",
              description:
                "You don't have access to any campus yet. Ask an administrator.",
            }
      }
    />
  );
}
