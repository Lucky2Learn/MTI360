import { parseTime, type Time } from "@internationalized/date";

// ISO time helpers for TimePicker (T00-07C). Public values are ISO 8601
// local times "HH:mm" (24-hour, minute precision) — matching DatePicker's ISO
// dates. No dates, no time zones, no conversion.

const ISO_TIME = /^([01]\d|2[0-3]):[0-5]\d$/;

/** "HH:mm" → Time; undefined stays undefined (uncontrolled), invalid → null. */
export function isoToTime(
  iso: string | null | undefined,
): Time | null | undefined {
  if (iso === undefined) return undefined;
  if (iso === null || !ISO_TIME.test(iso)) return null;
  return parseTime(iso);
}

/** Time → "HH:mm"; null stays null. */
export function timeToIso(
  time: { hour: number; minute: number } | null,
): string | null {
  if (!time) return null;
  return `${String(time.hour).padStart(2, "0")}:${String(time.minute).padStart(2, "0")}`;
}

/**
 * Literal segments (the space before am/pm) come from Intl formatToParts, and
 * ICU versions disagree on the space character: Node emits U+202F while some
 * browsers emit U+0020. Normalising Unicode spaces keeps server-rendered and
 * hydrated text identical (avoids a React hydration text mismatch).
 */
export function normalizeLiteral(text: string): string {
  return text.replace(/[  -   ]/g, " ");
}
