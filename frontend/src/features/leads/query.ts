import type { LeadStatus } from "@/lib/api/admissions";

import { first, offsetOf, type SearchParams } from "../courses/query";

import { PIPELINE, SOURCE_LABEL, STATUS_LABEL } from "./labels";

// URL → API queries for GROW-08 / ADM-02 (Phase 02-1; blueprint §22-§23).
// Only known keys with allowed values reach the API: IDs, enums and the
// search box term. Without a status filter the list shows open leads; the
// board always shows the open pipeline (one request per column).

export type LeadView = "list" | "board";
export const LEAD_PAGE_SIZE = 25;
export const BOARD_COLUMN_SIZE = 25;
export const ALL_STATUSES = "all";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const STATUSES = new Set(Object.keys(STATUS_LABEL));
const SOURCES = new Set(Object.keys(SOURCE_LABEL));
const FOLLOW_UPS = new Set(["overdue", "today", "upcoming", "none"]);
const SORTS = new Set([
  "-created_at",
  "created_at",
  "-updated_at",
  "full_name",
  "-full_name",
  "next_follow_up_at",
]);

export function viewOf(params: SearchParams): LeadView {
  return first(params.view) === "board" ? "board" : "list";
}

/** The statuses the list asks for: one, all, or (default) the open ones. */
export function statusesOf(params: SearchParams): LeadStatus[] | null {
  const status = first(params.status);
  if (status === ALL_STATUSES) return null;
  if (status && STATUSES.has(status)) return [status as LeadStatus];
  return PIPELINE;
}

/** The browser's offset east of UTC in minutes, sent with "today" filters. */
export function utcOffsetOf(params: SearchParams): number {
  const value = Number(first(params.utc_offset));
  return Number.isInteger(value) && value >= -720 && value <= 840 ? value : 0;
}

function filters(params: SearchParams): URLSearchParams {
  const query = new URLSearchParams();
  const q = first(params.q);
  if (q) query.set("q", q.slice(0, 200));
  const owner = first(params.owner);
  if (owner && (owner === "me" || owner === "unassigned" || UUID.test(owner))) {
    query.set("owner", owner);
  }
  const campus = first(params.campus);
  if (campus && (campus === "none" || UUID.test(campus)))
    query.set("campus", campus);
  const course = first(params.course);
  if (course && UUID.test(course)) query.set("course", course);
  const source = first(params.source);
  if (source && SOURCES.has(source)) query.set("source", source);
  const followUp = first(params.follow_up);
  if (followUp && FOLLOW_UPS.has(followUp)) query.set("follow_up", followUp);
  query.set("utc_offset", String(utcOffsetOf(params)));
  return query;
}

export function leadListQuery(params: SearchParams): string {
  const query = filters(params);
  for (const status of statusesOf(params) ?? []) query.append("status", status);
  const sort = first(params.sort);
  query.set("sort", sort && SORTS.has(sort) ? sort : "-created_at");
  query.set("limit", String(LEAD_PAGE_SIZE));
  query.set("offset", String(offsetOf(params.offset)));
  return query.toString();
}

export function boardColumnQuery(
  params: SearchParams,
  status: LeadStatus,
): string {
  const query = filters(params);
  query.set("status", status);
  query.set("sort", "-updated_at");
  query.set("limit", String(BOARD_COLUMN_SIZE));
  return query.toString();
}
