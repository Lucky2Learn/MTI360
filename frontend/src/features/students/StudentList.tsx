"use client";

import {
  DataTable,
  FilterBar,
  Pagination,
  Search,
  Select,
  type DataTableColumn,
  type SortDescriptor,
} from "@/design-system/components";
import type { StudentListItemWire } from "@/lib/api/admissions";
import type { PageMeta } from "@/lib/api/server-read";
import { useListParams } from "@/lib/navigation/list-params";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { studentPath } from "../applications/labels";
import { formatDate } from "../shared/format";
import { RecordLink } from "../shared/RecordLink";

// ADM-11 Students (Phase 02-2; ADR-0021 §6): students of the member's campuses
// (by home campus), newest first. Students are created only by approving an
// admission, so the list has no "New" action. Search: name, student number or
// email prefix (the search box term is the only text in the URL).

const SORTABLE = new Set(["full_name", "student_number", "created_at"]);

function sortDescriptor(sort: string | null): SortDescriptor {
  const value = sort ?? "-created_at";
  const columnId = value.replace(/^-/, "");
  return {
    columnId: SORTABLE.has(columnId) ? columnId : "created_at",
    direction: value.startsWith("-") ? "descending" : "ascending",
  };
}

export function StudentList({
  students,
  page,
}: {
  students: StudentListItemWire[];
  page: PageMeta;
}) {
  const params = useListParams();
  const { session } = useTenantSession();
  const q = params.get("q") ?? "";
  const campus = params.get("campus");

  const columns: DataTableColumn<StudentListItemWire>[] = [
    {
      id: "student_number",
      header: "Student number",
      isSortable: true,
      cell: (student) => (
        <span className="font-medium text-text-primary">
          {student.student_number}
        </span>
      ),
    },
    {
      id: "full_name",
      header: "Name",
      isSortable: true,
      isRowHeader: true,
      cell: (student) => (
        <RecordLink href={studentPath(student.id)}>
          {student.full_name}
        </RecordLink>
      ),
    },
    {
      id: "course",
      header: "Latest course",
      cell: (student) => student.latest_course ?? "—",
    },
    {
      id: "campus",
      header: "Home campus",
      visibleFrom: "tablet",
      cell: (s) => s.campus_code,
    },
    {
      id: "admissions",
      header: "Admissions",
      visibleFrom: "tablet",
      cell: (student) => String(student.admissions),
    },
    {
      id: "created_at",
      header: "Since",
      isSortable: true,
      visibleFrom: "desktop",
      cell: (student) => formatDate(student.created_at),
    },
  ];

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <FilterBar
        label="Student filters"
        search={
          <Search
            label="Search students"
            isLabelHidden
            placeholder="Search by name or student number"
            defaultValue={q}
            onSubmit={(value) => params.set({ q: value.trim() || null })}
            onClear={() => params.set({ q: null })}
          />
        }
        activeFilterCount={campus ? 1 : 0}
        resultCount={`${page.total} ${page.total === 1 ? "student" : "students"}`}
        onClear={() => params.set({ campus: null })}
        filters={
          <Select
            label="Home campus"
            options={[
              { id: "any", label: "Any campus" },
              ...session.campusOptions.map((c) => ({
                id: c.id,
                label: c.name,
              })),
            ]}
            value={campus ?? "any"}
            onChange={(value) =>
              params.set({ campus: value === "any" ? null : value })
            }
          />
        }
      />
      <DataTable
        label="Students"
        columns={columns}
        rows={students}
        getRowId={(student) => student.id}
        getRowLabel={(student) => student.full_name}
        mobileLayout="cards"
        sort={sortDescriptor(params.get("sort"))}
        onSortChange={(sort) =>
          params.set({
            sort: sort
              ? `${sort.direction === "descending" ? "-" : ""}${sort.columnId}`
              : null,
          })
        }
        emptyState={
          q || campus
            ? {
                title: "No students match this search",
                description: "Try another name or student number.",
              }
            : {
                title: "No students yet",
                description:
                  "Students are created when an admission is approved on an application.",
              }
        }
        footer={
          page.total > page.limit ? (
            <Pagination
              label="Student pages"
              itemLabel="students"
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
