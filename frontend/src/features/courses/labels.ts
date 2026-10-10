import type { Tone } from "@/design-system/components";
import type {
  CourseCategory,
  CourseStatus,
  CourseWire,
  DurationUnit,
} from "@/lib/api/admissions";

// Course catalogue copy (Phase 02-1; ACA-01/02/03). Display only.

export const COURSES_PATH = "/app/academics/courses";
export const COURSE_MANAGE = "course.manage";
export const COURSE_READ = "course.read";

export const CATEGORY_LABEL: Record<CourseCategory, string> = {
  PRE_SEA: "Pre-sea",
  POST_SEA: "Post-sea",
  OTHER: "Other",
};

export const STATUS_LABEL: Record<CourseStatus, string> = {
  DRAFT: "Draft",
  ACTIVE: "Active",
  ARCHIVED: "Archived",
};

export const STATUS_TONE: Record<CourseStatus, Tone> = {
  DRAFT: "neutral",
  ACTIVE: "success",
  ARCHIVED: "warning",
};

export const UNIT_LABEL: Record<DurationUnit, [string, string]> = {
  DAYS: ["day", "days"],
  WEEKS: ["week", "weeks"],
  MONTHS: ["month", "months"],
  YEARS: ["year", "years"],
};

export function durationLabel(
  course: Pick<CourseWire, "duration_value" | "duration_unit">,
): string | null {
  const { duration_value: value, duration_unit: unit } = course;
  if (value === null || unit === null) return null;
  return `${value} ${UNIT_LABEL[unit][value === 1 ? 0 : 1]}`;
}

export const coursePath = (id: string) => `${COURSES_PATH}/${id}`;
