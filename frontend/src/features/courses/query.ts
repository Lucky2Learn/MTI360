// URL → API query for ACA-01 (Phase 02-1; blueprint §23). Only known keys
// with allowed values are forwarded; anything else in the URL is dropped
// rather than turned into an API validation error.

export type SearchParams = Record<string, string | string[] | undefined>;

const STATUSES = new Set(["DRAFT", "ACTIVE", "ARCHIVED"]);
const CATEGORIES = new Set(["PRE_SEA", "POST_SEA", "OTHER"]);
const SORTS = new Set(["name", "-name", "code", "-code"]);
export const COURSE_PAGE_SIZE = 25;

export function first(value: string | string[] | undefined): string | null {
  const item = Array.isArray(value) ? value[0] : value;
  return item && item.trim() ? item.trim() : null;
}

export function offsetOf(value: string | string[] | undefined): number {
  const number = Number(first(value));
  return Number.isInteger(number) && number > 0 && number <= 10_000
    ? number
    : 0;
}

export function courseListQuery(params: SearchParams): string {
  const query = new URLSearchParams();
  const q = first(params.q);
  if (q) query.set("q", q.slice(0, 200));
  const status = first(params.status);
  if (status && STATUSES.has(status)) query.set("status", status);
  const category = first(params.category);
  if (category && CATEGORIES.has(category)) query.set("category", category);
  const sort = first(params.sort);
  query.set("sort", sort && SORTS.has(sort) ? sort : "name");
  query.set("limit", String(COURSE_PAGE_SIZE));
  query.set("offset", String(offsetOf(params.offset)));
  return query.toString();
}
