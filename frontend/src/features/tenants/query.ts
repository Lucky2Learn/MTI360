import { first, offsetOf, type SearchParams } from "@/features/courses/query";

import { TENANT_STATUSES } from "./labels";

// URL → API query for the platform tenant list (PLAT-04). Only known keys
// with allowed values are forwarded (GET /platform/tenants: q, status, sort,
// limit, offset); anything else in the URL is dropped rather than turned
// into an API validation error. The list's sort indicator reads the same
// `tenantSort`, so it always shows the order the API was asked for.

export type { SearchParams };

const SORTS = new Set(["name", "-name", "created_at", "-created_at"]);
export const TENANT_PAGE_SIZE = 25;
export const DEFAULT_TENANT_SORT = "-created_at";

/** The sort sent to the API for a URL value (unknown → the default). */
export function tenantSort(value: string | null): string {
  return value && SORTS.has(value) ? value : DEFAULT_TENANT_SORT;
}

export function tenantListQuery(params: SearchParams): string {
  const query = new URLSearchParams();
  const q = first(params.q);
  if (q) query.set("q", q.slice(0, 200));
  const status = first(params.status);
  if (status && (TENANT_STATUSES as readonly string[]).includes(status)) {
    query.set("status", status);
  }
  query.set("sort", tenantSort(first(params.sort)));
  query.set("limit", String(TENANT_PAGE_SIZE));
  // A hand-edited offset starts its page, so the page number is exact.
  const offset = offsetOf(params.offset);
  query.set("offset", String(offset - (offset % TENANT_PAGE_SIZE)));
  return query.toString();
}
