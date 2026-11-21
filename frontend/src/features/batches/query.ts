// URL → API query for ACA-05 (Phase 02-6). Only known keys with allowed
// values are forwarded; anything else in the URL is dropped.

import { first, offsetOf, type SearchParams } from "../courses/query";

export type { SearchParams };

const STATUSES = new Set(["OPEN", "CLOSED", "CANCELLED"]);
const SEATS = new Set(["true", "false"]);
const SORTS = new Set([
  "start_date",
  "-start_date",
  "code",
  "-code",
  "name",
  "-name",
]);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const BATCH_PAGE_SIZE = 25;

export function batchListQuery(params: SearchParams): string {
  const query = new URLSearchParams();
  const q = first(params.q);
  if (q) query.set("q", q.slice(0, 200));
  const status = first(params.status);
  if (status && STATUSES.has(status)) query.set("status", status);
  for (const key of ["course_id", "campus_id"] as const) {
    const value = first(params[key]);
    if (value && UUID.test(value)) query.set(key, value);
  }
  const hasSeats = first(params.has_seats);
  if (hasSeats && SEATS.has(hasSeats)) query.set("has_seats", hasSeats);
  const sort = first(params.sort);
  query.set("sort", sort && SORTS.has(sort) ? sort : "-start_date");
  query.set("limit", String(BATCH_PAGE_SIZE));
  query.set("offset", String(offsetOf(params.offset)));
  return query.toString();
}
