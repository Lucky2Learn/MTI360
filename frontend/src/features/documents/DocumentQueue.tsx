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
import type { QueueItemWire } from "@/lib/api/admissions";
import type { PageMeta } from "@/lib/api/server-read";
import { useListParams } from "@/lib/navigation/list-params";

import {
  applicationPath,
  DOCUMENT_STATUS_LABEL,
  DOCUMENT_STATUS_TONE,
  DOCUMENT_TYPE_LABEL,
  fileSize,
} from "../applications/labels";
import { formatDateTime } from "../shared/format";
import { RecordLink } from "../shared/RecordLink";

import { DownloadLink } from "./DocumentsPanel";

// ADM-09 Document verification queue (Phase 02-2; ADR-0021 §5): current
// documents of the member's campuses, oldest first, awaiting verification by
// default. Verifiers decide on the application page, next to the applicant's
// details and the other documents (ADM-06), where the API checks again.

export function DocumentQueue({
  items,
  page,
}: {
  items: QueueItemWire[];
  page: PageMeta;
}) {
  const params = useListParams();
  const q = params.get("q") ?? "";
  const status = params.get("status") ?? "UNDER_REVIEW";

  const columns: DataTableColumn<QueueItemWire>[] = [
    {
      id: "document",
      header: "Document",
      isRowHeader: true,
      cell: (item) => (
        <span className="flex flex-col gap-1">
          <span className="font-medium text-text-primary">
            {DOCUMENT_TYPE_LABEL[item.document_type]}
          </span>
          <DownloadLink document={item} />
        </span>
      ),
    },
    {
      id: "applicant",
      header: "Applicant",
      cell: (item) => (
        <span className="flex flex-col gap-1">
          <RecordLink href={`${applicationPath(item.application_id)}`}>
            {item.applicant_name}
          </RecordLink>
          <span className="text-caption text-text-secondary">
            {item.application_number}
          </span>
        </span>
      ),
    },
    {
      id: "course",
      header: "Course",
      visibleFrom: "tablet",
      cell: (item) => item.course_code,
    },
    {
      id: "campus",
      header: "Campus",
      visibleFrom: "tablet",
      cell: (item) => item.campus_code,
    },
    {
      id: "uploaded",
      header: "Uploaded",
      visibleFrom: "desktop",
      cell: (item) =>
        `${formatDateTime(item.created_at)}${item.uploaded_by ? ` · ${item.uploaded_by}` : ""} · ${fileSize(item.size_bytes)}`,
    },
    {
      id: "status",
      header: "Status",
      cell: (item) => (
        <Badge tone={DOCUMENT_STATUS_TONE[item.status]}>
          {DOCUMENT_STATUS_LABEL[item.status]}
        </Badge>
      ),
    },
  ];

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <FilterBar
        label="Document filters"
        search={
          <Search
            label="Search by applicant"
            isLabelHidden
            placeholder="Search by applicant or application number"
            defaultValue={q}
            onSubmit={(value) => params.set({ q: value.trim() || null })}
            onClear={() => params.set({ q: null })}
          />
        }
        activeFilterCount={status === "UNDER_REVIEW" ? 0 : 1}
        resultCount={`${page.total} ${page.total === 1 ? "document" : "documents"}`}
        onClear={() => params.set({ status: null })}
        filters={
          <Select
            label="Status"
            options={(
              ["UNDER_REVIEW", "UPLOADED", "REJECTED", "VERIFIED"] as const
            ).map((value) => ({
              id: value,
              label: DOCUMENT_STATUS_LABEL[value],
            }))}
            value={status}
            onChange={(value) =>
              params.set({ status: value === "UNDER_REVIEW" ? null : value })
            }
          />
        }
      />
      <DataTable
        label="Documents"
        columns={columns}
        rows={items}
        getRowId={(item) => item.id}
        getRowLabel={(item) =>
          `${DOCUMENT_TYPE_LABEL[item.document_type]} ${item.applicant_name}`
        }
        mobileLayout="cards"
        emptyState={
          q || status !== "UNDER_REVIEW"
            ? {
                title: "No documents match these filters",
                description: "Try another search term or status.",
                action: (
                  <Button
                    variant="secondary"
                    onPress={() => params.set({ q: null, status: null })}
                  >
                    Clear filters
                  </Button>
                ),
              }
            : {
                title: "Nothing to verify",
                description:
                  "Documents of submitted applications appear here until they are verified or rejected.",
              }
        }
        footer={
          page.total > page.limit ? (
            <Pagination
              label="Document pages"
              itemLabel="documents"
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
