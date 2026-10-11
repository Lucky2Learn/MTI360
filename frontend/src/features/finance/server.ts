import "server-only";

import type { CourseWire } from "@/lib/api/admissions";
import { tenantApiRead } from "@/lib/api/server-read";
import type { CampusWire, SessionWire } from "@/lib/api/types";
import { can } from "@/lib/authz/requirements";

import type { FilterOption } from "./InvoiceList";

// Server reads shared by the finance list pages (Phase 02-5). Filter options
// are a convenience: a member without course.read gets no course filter, and
// a failed read leaves it out rather than failing the page. The API still
// scopes every row to the tenant and the caller's campuses.

const COURSE_READ = "course.read";

export async function courseFilterOptions(
  session: SessionWire,
): Promise<FilterOption[]> {
  if (!can(session.permissions, COURSE_READ)) return [];
  const read = await tenantApiRead<CourseWire[]>(
    "/courses?status=ACTIVE&status=DRAFT&status=ARCHIVED&sort=name&limit=100",
  );
  if (read.kind !== "ok") return [];
  return read.data.map((course) => ({
    id: course.id,
    label: `${course.code} · ${course.name}`,
  }));
}

/** The campuses the caller works with (the session's options). */
export function sessionCampuses(session: SessionWire): CampusWire[] {
  return session.campus_options;
}
