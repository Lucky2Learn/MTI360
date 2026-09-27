import { describe, expect, it } from "vitest";

import {
  calendarDateToIso,
  isoToCalendarDate,
  MTI360_DEFAULT_LOCALE,
  MTI360_FIRST_DAY_OF_WEEK,
} from "./date";

describe("DatePicker ISO helpers", () => {
  it("round-trips valid ISO dates", () => {
    for (const iso of [
      "2026-09-27",
      "2000-02-29",
      "1999-12-31",
      "2026-01-05",
    ]) {
      expect(calendarDateToIso(isoToCalendarDate(iso)!)).toBe(iso);
    }
  });

  it("keeps undefined (uncontrolled) and null (empty) distinct", () => {
    expect(isoToCalendarDate(undefined)).toBeUndefined();
    expect(isoToCalendarDate(null)).toBeNull();
    expect(calendarDateToIso(null)).toBeNull();
  });

  it.each([
    "",
    "27/09/2026",
    "2026-9-27",
    "2026-02-31",
    "2025-02-29",
    "2026-13-01",
    "not a date",
  ])("treats %j as invalid (null)", (value) => {
    expect(isoToCalendarDate(value)).toBeNull();
  });

  it("pads years, months and days", () => {
    expect(calendarDateToIso({ year: 987, month: 3, day: 4 })).toBe(
      "0987-03-04",
    );
  });

  it("uses en-IN formatting with the MTI 360 Monday-first product default", () => {
    expect(MTI360_DEFAULT_LOCALE).toBe("en-IN");
    expect(MTI360_FIRST_DAY_OF_WEEK).toBe("mon");
  });
});
