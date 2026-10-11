import { describe, expect, it } from "vitest";

import { istToday } from "./today";

// The IST calendar date used as the due-date and received-on bound (Phase
// 02-5; readiness plan §12): midnight in India is 18:30 UTC the day before.

describe("istToday", () => {
  it.each([
    ["2027-03-31T18:29:59.999Z", "2027-03-31"],
    ["2027-03-31T18:30:00.000Z", "2027-04-01"],
    ["2026-12-31T18:30:00.000Z", "2027-01-01"],
    ["2026-10-11T00:00:00.000Z", "2026-10-11"],
  ])("%s is %s in India", (instant, date) => {
    expect(istToday(new Date(instant))).toBe(date);
  });
});
