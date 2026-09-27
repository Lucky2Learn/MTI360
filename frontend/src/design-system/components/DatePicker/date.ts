import { parseDate, type CalendarDate } from "@internationalized/date";

// ISO date helpers for DatePicker (T00-07B, decision D2). The public API uses
// ISO 8601 calendar dates ("2026-09-27"), matching backend `date` fields;
// @internationalized/date stays an implementation detail of this folder.
// Dates only: no times, no time zones.

export const MTI360_DEFAULT_LOCALE = "en-IN";

/**
 * MTI 360 product default (T00-07 D10, confirmed by T00-07B D3): weeks start
 * on Monday. This is deliberately independent of the locale: CLDR's en-IN
 * default is Sunday, but MTI 360 uses Monday unless a screen explicitly
 * passes another `firstDayOfWeek` (INC-20).
 */
export const MTI360_FIRST_DAY_OF_WEEK = "mon";

export type FirstDayOfWeek =
  "sun" | "mon" | "tue" | "wed" | "thu" | "fri" | "sat";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** ISO string → CalendarDate; undefined stays undefined (uncontrolled), invalid → null. */
export function isoToCalendarDate(
  iso: string | null | undefined,
): CalendarDate | null | undefined {
  if (iso === undefined) return undefined;
  if (iso === null || !ISO_DATE.test(iso)) return null;
  try {
    const date = parseDate(iso);
    // parseDate constrains out-of-range days (2026-02-31); reject instead.
    return date.toString() === iso ? date : null;
  } catch {
    return null;
  }
}

/** CalendarDate (or any date value) → ISO "YYYY-MM-DD"; null stays null. */
export function calendarDateToIso(
  date: { year: number; month: number; day: number } | null,
): string | null {
  if (!date) return null;
  const pad = (value: number, length: number) =>
    String(value).padStart(length, "0");
  return `${pad(date.year, 4)}-${pad(date.month, 2)}-${pad(date.day, 2)}`;
}
