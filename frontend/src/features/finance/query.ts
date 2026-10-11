// URL → API query for the finance lists (Phase 02-5; readiness plan §4).
// Only known keys with allowed values are forwarded; anything else in the
// URL is dropped rather than turned into an API validation error.

import { first, offsetOf, type SearchParams } from "@/features/courses/query";

export type { SearchParams };

export const FINANCE_PAGE_SIZE = 25;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function page(query: URLSearchParams, params: SearchParams): string {
  query.set("limit", String(FINANCE_PAGE_SIZE));
  query.set("offset", String(offsetOf(params.offset)));
  return query.toString();
}

function pick(
  query: URLSearchParams,
  params: SearchParams,
  key: string,
  allowed: ReadonlySet<string> | RegExp,
): void {
  const value = first(params[key]);
  if (!value) return;
  const ok =
    allowed instanceof RegExp ? allowed.test(value) : allowed.has(value);
  if (ok) query.set(key, value);
}

function search(query: URLSearchParams, params: SearchParams): void {
  const q = first(params.q);
  if (q) query.set("q", q.slice(0, 200));
}

function sort(
  query: URLSearchParams,
  params: SearchParams,
  allowed: ReadonlySet<string>,
  fallback: string,
): void {
  const value = first(params.sort);
  query.set("sort", value && allowed.has(value) ? value : fallback);
}

const STRUCTURE_STATUSES = new Set(["DRAFT", "ACTIVE", "ARCHIVED"]);
const STRUCTURE_SORTS = new Set(["name", "-name", "updated_at", "-updated_at"]);

export function structureListQuery(params: SearchParams): string {
  const query = new URLSearchParams();
  search(query, params);
  pick(query, params, "status", STRUCTURE_STATUSES);
  pick(query, params, "course_id", UUID);
  sort(query, params, STRUCTURE_SORTS, "name");
  return page(query, params);
}

const INVOICE_STATUSES = new Set([
  "ISSUED",
  "PARTIALLY_PAID",
  "PAID",
  "CANCELLED",
]);
const INVOICE_SORTS = new Set([
  "issued_at",
  "-issued_at",
  "due_date",
  "-due_date",
  "number",
  "-number",
  "balance",
  "-balance",
]);
const FLAGS = new Set(["true"]);

/** FIN-04 Invoices; with `outstanding`, FIN-08 (unpaid balances, oldest due first). */
export function invoiceListQuery(
  params: SearchParams,
  { outstanding = false }: { outstanding?: boolean } = {},
): string {
  const query = new URLSearchParams();
  search(query, params);
  if (!outstanding) pick(query, params, "status", INVOICE_STATUSES);
  pick(query, params, "campus_id", UUID);
  pick(query, params, "course_id", UUID);
  pick(query, params, "due_from", ISO_DATE);
  pick(query, params, "due_to", ISO_DATE);
  pick(query, params, "overdue", FLAGS);
  if (outstanding) query.set("outstanding", "true");
  sort(query, params, INVOICE_SORTS, outstanding ? "due_date" : "-issued_at");
  return page(query, params);
}

const PAYMENT_STATUSES = new Set([
  "PENDING",
  "CONFIRMED",
  "FAILED",
  "REVERSED",
]);
const METHODS = new Set([
  "CASH",
  "UPI",
  "BANK_TRANSFER",
  "CHEQUE",
  "DEMAND_DRAFT",
]);
const PAYMENT_SORTS = new Set([
  "created_at",
  "-created_at",
  "received_on",
  "-received_on",
  "amount",
  "-amount",
]);

export function paymentListQuery(params: SearchParams): string {
  const query = new URLSearchParams();
  search(query, params);
  pick(query, params, "status", PAYMENT_STATUSES);
  pick(query, params, "method", METHODS);
  pick(query, params, "campus_id", UUID);
  pick(query, params, "received_from", ISO_DATE);
  pick(query, params, "received_to", ISO_DATE);
  sort(query, params, PAYMENT_SORTS, "-created_at");
  return page(query, params);
}

export function isRecordId(value: string | null): value is string {
  return value !== null && UUID.test(value);
}
