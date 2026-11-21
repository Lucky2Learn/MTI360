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
import type { PageMeta } from "@/lib/api/server-read";
import type { MemberWire } from "@/lib/api/tenant-admin";
import { useListParams } from "@/lib/navigation/list-params";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { formatDate } from "../shared/format";
import { RecordLink } from "../shared/RecordLink";

import { InviteMemberButton } from "./InviteMemberDialog";
import {
  campusAccessLabel,
  isOwnMembership,
  MEMBER_INVITE,
  memberPath,
  STATUS_LABEL,
  STATUS_TONE,
} from "./labels";

// ADMIN-05 Users (02-C; GET /members, member.read): the institute's
// members. Search (name or email), status filter, sort and page live in the
// URL; the server renders the page. "Invite member" is offered only with
// member.invite (UX only; the API refuses the request anyway).

const ANY = "any";
/** Column → API sort field (GET /members allows these four). */
const SORTS: Record<string, string> = {
  name: "display_name",
  email: "email",
  status: "status",
  invited: "created_at",
};

function sortDescriptor(sort: string | null): SortDescriptor {
  const value = sort ?? "display_name";
  const field = value.replace(/^-/, "");
  const columnId =
    Object.keys(SORTS).find((column) => SORTS[column] === field) ?? "name";
  return {
    columnId,
    direction: value.startsWith("-") ? "descending" : "ascending",
  };
}

export function MemberList({
  members,
  page,
}: {
  members: MemberWire[];
  page: PageMeta;
}) {
  const params = useListParams();
  const { session, can } = useTenantSession();
  const q = params.get("q") ?? "";
  const status = params.get("status");
  const filtered = Boolean(q || status);

  const columns: DataTableColumn<MemberWire>[] = [
    {
      id: "name",
      header: "Name",
      isSortable: true,
      isRowHeader: true,
      cell: (member) => (
        <span className="flex min-w-0 flex-col gap-0.5">
          <RecordLink href={memberPath(member.id)}>
            {member.user.display_name}
          </RecordLink>
          {isOwnMembership(member, session.user.email) && (
            <span className="text-caption text-text-secondary">You</span>
          )}
        </span>
      ),
    },
    {
      id: "email",
      header: "Email",
      isSortable: true,
      visibleFrom: "tablet",
      cell: (member) => <span className="break-all">{member.user.email}</span>,
    },
    {
      id: "roles",
      header: "Roles",
      visibleFrom: "desktop",
      cell: (member) =>
        member.roles.length > 0
          ? member.roles.map((role) => role.name).join(", ")
          : "No roles",
    },
    {
      id: "campuses",
      header: "Campus access",
      visibleFrom: "desktop",
      cell: (member) => campusAccessLabel(member),
    },
    {
      id: "status",
      header: "Status",
      isSortable: true,
      cell: (member) => (
        <Badge tone={STATUS_TONE[member.status]}>
          {STATUS_LABEL[member.status]}
        </Badge>
      ),
    },
    {
      id: "invited",
      header: "Invited",
      isSortable: true,
      visibleFrom: "desktop",
      cell: (member) => formatDate(member.invited_at),
    },
  ];

  // A page past the end (a stale link after members changed) is not "empty".
  const emptyState =
    page.total > 0
      ? {
          title: "No members on this page",
          description: "The list has fewer pages than this link expects.",
          action: (
            <Button variant="secondary" onPress={() => params.set({})}>
              Go to the first page
            </Button>
          ),
        }
      : filtered
        ? {
            title: "No members match these filters",
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
        : can(MEMBER_INVITE)
          ? {
              title: "No members yet",
              description:
                "Invite your team, such as counsellors and admissions staff, so they can sign in.",
              action: <InviteMemberButton />,
            }
          : {
              title: "No members yet",
              description:
                "Members appear here once your institute invites them.",
            };

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <FilterBar
        label="Member filters"
        search={
          <Search
            label="Search members"
            isLabelHidden
            placeholder="Search by name or email"
            defaultValue={q}
            onSubmit={(value) => params.set({ q: value.trim() || null })}
            onClear={() => params.set({ q: null })}
          />
        }
        activeFilterCount={status ? 1 : 0}
        resultCount={`${page.total} ${page.total === 1 ? "member" : "members"}`}
        onClear={() => params.set({ status: null })}
        filters={
          <Select
            label="Status"
            options={[
              { id: ANY, label: "Any status" },
              { id: "ACTIVE", label: STATUS_LABEL.ACTIVE },
              { id: "INVITED", label: STATUS_LABEL.INVITED },
              { id: "SUSPENDED", label: STATUS_LABEL.SUSPENDED },
              { id: "REVOKED", label: STATUS_LABEL.REVOKED },
            ]}
            value={status ?? ANY}
            onChange={(value) =>
              params.set({ status: value === ANY ? null : value })
            }
          />
        }
      />
      <DataTable
        label="Members"
        columns={columns}
        rows={members}
        getRowId={(member) => member.id}
        getRowLabel={(member) => member.user.display_name}
        mobileLayout="cards"
        sort={sortDescriptor(params.get("sort"))}
        onSortChange={(sort) =>
          params.set({
            sort:
              sort && SORTS[sort.columnId]
                ? `${sort.direction === "descending" ? "-" : ""}${SORTS[sort.columnId]}`
                : null,
          })
        }
        emptyState={emptyState}
        footer={
          page.total > page.limit ? (
            <Pagination
              label="Member pages"
              itemLabel="members"
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
