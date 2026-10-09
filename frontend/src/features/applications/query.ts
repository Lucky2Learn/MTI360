import { first, offsetOf, type SearchParams } from "../courses/query";

import { STATUS_FILTERS } from "./labels";

// URL → API queries for ADM-05 Applications, ADM-09 Documents and ADM-11
// Students (Phase 02-2). Only known keys with allowed values are forwarded:
// IDs, enums and the search box term; anything else in the URL is dropped
// rather than turned into an API validation error.

export const PAGE_SIZE = 25;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const APPLICATION_SORTS = new Set([
  "-created_at",
  "created_at",
  "-submitted_at",
  "full_name",
  "-full_name",
  "number",
  "-number",
]);
const DOCUMENT_STATUSES = new Set([
  "UPLOADED",
  "UNDER_REVIEW",
  "VERIFIED",
  "REJECTED",
]);
const STUDENT_SORTS = new Set([
  "-created_at",
  "full_name",
  "-full_name",
  "student_number",
]);

function base(params: SearchParams, sort: string): URLSearchParams {
  const query = new URLSearchParams();
  const q = first(params.q);
  if (q) query.set("q", q.slice(0, 200));
  query.set("sort", sort);
  query.set("limit", String(PAGE_SIZE));
  query.set("offset", String(offsetOf(params.offset)));
  return query;
}

export function applicationListQuery(params: SearchParams): string {
  const sort = first(params.sort);
  const query = base(
    params,
    sort && APPLICATION_SORTS.has(sort) ? sort : "-created_at",
  );
  const status = first(params.status);
  if (status && (STATUS_FILTERS as string[]).includes(status)) {
    query.set("status", status);
  }
  if (first(params.owner) === "me") query.set("owner", "me");
  const lead = first(params.lead);
  if (lead && UUID.test(lead)) query.set("lead", lead);
  return query.toString();
}

export function documentQueueQuery(params: SearchParams): string {
  const query = base(params, "created_at");
  query.delete("sort"); // the queue is always oldest first
  const status = first(params.status);
  query.set(
    "status",
    status && DOCUMENT_STATUSES.has(status) ? status : "UNDER_REVIEW",
  );
  return query.toString();
}

export function studentListQuery(params: SearchParams): string {
  const sort = first(params.sort);
  const query = base(
    params,
    sort && STUDENT_SORTS.has(sort) ? sort : "-created_at",
  );
  const campus = first(params.campus);
  if (campus && UUID.test(campus)) query.set("campus", campus);
  return query.toString();
}
