// Today's date in India Standard Time, "YYYY-MM-DD" (Phase 02-5). Fee due
// dates and received-on dates are IST calendar dates (readiness plan §12,
// INC-40). Used only as a date-picker bound for quick feedback: the server
// checks both dates against its own IST date and its answer wins.

const IST = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Kolkata",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

export function istToday(now: Date = new Date()): string {
  return IST.format(now);
}
