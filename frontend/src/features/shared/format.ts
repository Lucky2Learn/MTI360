// Display formatting shared by business screens (Phase 02-1). Indian English,
// fixed patterns; the browser's time zone. Values only — never used for logic.

const DATE = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

const DATE_TIME = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

function parsed(iso: string): Date | null {
  const value = new Date(iso);
  return Number.isNaN(value.getTime()) ? null : value;
}

/** "8 Oct 2026". Date-only values ("2007-05-14") are read as calendar dates. */
export function formatDate(iso: string): string {
  const value = /^\d{4}-\d{2}-\d{2}$/.test(iso)
    ? parsed(`${iso}T00:00:00`)
    : parsed(iso);
  return value ? DATE.format(value) : "";
}

/** "8 Oct 2026, 10:00 am". */
export function formatDateTime(iso: string): string {
  const value = parsed(iso);
  return value ? DATE_TIME.format(value) : "";
}
