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
  type SortDescriptor,
} from "@/design-system/components";
import { AddIcon } from "@/design-system/icons";
import type { CourseWire } from "@/lib/api/admissions";
import type { PageMeta } from "@/lib/api/server-read";
import { PermissionGate } from "@/lib/authz/PermissionGate";
import { useListParams } from "@/lib/navigation/list-params";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { RecordLink } from "../shared/RecordLink";

import {
  CATEGORY_LABEL,
  COURSE_MANAGE,
  COURSES_PATH,
  coursePath,
  durationLabel,
  STATUS_LABEL,
  STATUS_TONE,
} from "./labels";

// ACA-01 Courses (Phase 02-1; blueprint §21): the institute catalogue for
// every member with course.read (campus-restricted staff included). Search,
// status and category filters and sort live in the URL; the server renders
// the page. "New course" is offered only with course.manage (UX only; the
// API refuses the request anyway).

const ANY = "any";
const SORTS: Record<string, string> = { name: "name", code: "code" };

export function NewCourseButton() {
  return (
    <PermissionGate permission={COURSE_MANAGE}>
      <Button href={`${COURSES_PATH}/new`} iconStart={AddIcon}>
        New course
      </Button>
    </PermissionGate>
  );
}

function sortDescriptor(sort: string | null): SortDescriptor {
  const value = sort ?? "name";
  const descending = value.startsWith("-");
  const columnId = value.replace(/^-/, "");
  return {
    columnId: columnId in SORTS ? columnId : "name",
    direction: descending ? "descending" : "ascending",
  };
}

export function CourseList({
  courses,
  page,
}: {
  courses: CourseWire[];
  page: PageMeta;
}) {
  const params = useListParams();
  const { can } = useTenantSession();
  const q = params.get("q") ?? "";
  const status = params.get("status");
  const category = params.get("category");
  const filtered = Boolean(q || status || category);
  const activeFilters = [status, category].filter(Boolean).length;

  const columns: DataTableColumn<CourseWire>[] = [
    {
      id: "code",
      header: "Code",
      isSortable: true,
      cell: (course) => (
        <span className="font-medium text-text-primary">{course.code}</span>
      ),
    },
    {
      id: "name",
      header: "Course",
      isSortable: true,
      isRowHeader: true,
      cell: (course) => (
        <RecordLink href={coursePath(course.id)}>{course.name}</RecordLink>
      ),
    },
    {
      id: "category",
      header: "Category",
      cell: (course) => CATEGORY_LABEL[course.category],
    },
    {
      id: "duration",
      header: "Duration",
      visibleFrom: "tablet",
      cell: (course) => durationLabel(course) ?? "—",
    },
    {
      id: "status",
      header: "Status",
      cell: (course) => (
        <Badge tone={STATUS_TONE[course.status]}>
          {STATUS_LABEL[course.status]}
        </Badge>
      ),
    },
  ];

  const emptyState = filtered
    ? {
        title: "No courses match these filters",
        description: "Try another search term or clear the filters.",
        action: (
          <Button
            variant="secondary"
            onPress={() =>
              params.set({ q: null, status: null, category: null })
            }
          >
            Clear filters
          </Button>
        ),
      }
    : can(COURSE_MANAGE)
      ? {
          title: "No courses yet",
          description:
            "Create your first course so counsellors can record what enquirers are interested in.",
          action: <NewCourseButton />,
        }
      : {
          title: "No courses yet",
          description: "Courses appear here once your institute adds them.",
        };

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <FilterBar
        label="Course filters"
        search={
          <Search
            label="Search courses"
            isLabelHidden
            placeholder="Search by name or code"
            defaultValue={q}
            onSubmit={(value) => params.set({ q: value.trim() || null })}
            onClear={() => params.set({ q: null })}
          />
        }
        activeFilterCount={activeFilters}
        resultCount={`${page.total} ${page.total === 1 ? "course" : "courses"}`}
        onClear={() => params.set({ status: null, category: null })}
        filters={
          <>
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
            <Select
              label="Category"
              options={[
                { id: ANY, label: "Any category" },
                { id: "PRE_SEA", label: "Pre-sea" },
                { id: "POST_SEA", label: "Post-sea" },
                { id: "OTHER", label: "Other" },
              ]}
              value={category ?? ANY}
              onChange={(value) =>
                params.set({ category: value === ANY ? null : value })
              }
            />
          </>
        }
      />
      <DataTable
        label="Courses"
        columns={columns}
        rows={courses}
        getRowId={(course) => course.id}
        getRowLabel={(course) => course.name}
        mobileLayout="cards"
        sort={sortDescriptor(params.get("sort"))}
        onSortChange={(sort) =>
          params.set({
            sort: sort
              ? `${sort.direction === "descending" ? "-" : ""}${sort.columnId}`
              : null,
          })
        }
        emptyState={emptyState}
        footer={
          page.total > page.limit ? (
            <Pagination
              label="Course pages"
              itemLabel="courses"
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
