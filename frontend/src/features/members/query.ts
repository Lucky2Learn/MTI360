import { first, offsetOf, type SearchParams } from "../courses/query";

// URL → API query for ADMIN-05 Users (GET /members). Only known keys with
// allowed values are forwarded; anything else in the URL is dropped rather
// than turned into an API validation error.

const STATUSES = new Set(["INVITED", "ACTIVE", "SUSPENDED", "REVOKED"]);
const SORT_FIELDS = ["display_name", "email", "status", "created_at"];
const SORTS = new Set(SORT_FIELDS.flatMap((field) => [field, `-${field}`]));
export const MEMBER_PAGE_SIZE = 25;

export function memberListQuery(params: SearchParams): string {
  const query = new URLSearchParams();
  const q = first(params.q);
  if (q) query.set("q", q.slice(0, 200));
  const status = first(params.status);
  if (status && STATUSES.has(status)) query.set("status", status);
  const sort = first(params.sort);
  query.set("sort", sort && SORTS.has(sort) ? sort : "display_name");
  query.set("limit", String(MEMBER_PAGE_SIZE));
  query.set("offset", String(offsetOf(params.offset)));
  return query.toString();
}
