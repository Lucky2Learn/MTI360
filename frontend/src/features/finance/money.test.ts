import { describe, expect, it } from "vitest";

import { formatPaise, MAX_AMOUNT_MINOR, paiseInput, parsePaise } from "./money";

// Paise handling (Phase 02-5; ADR-0022 §6): string-only conversion, no floats.

describe("parsePaise", () => {
  it.each([
    ["0", 0],
    ["1", 100],
    ["1.5", 150],
    ["1.05", 105],
    ["0.10", 10],
    ["125000", 12_500_000],
    ["1,25,000", 12_500_000],
    ["1,25,000.50", 12_500_050],
    ["125,000.50", 12_500_050],
    ["₹ 2,50,000", 25_000_000],
    ["  42.00 ", 4200],
    ["007", 700],
    ["1000000000", MAX_AMOUNT_MINOR],
    // A value whose float arithmetic would round: 0.29 * 100 = 28.999999999999996.
    ["0.29", 29],
    ["1234567.89", 123_456_789],
  ])("%s → %d paise", (input, expected) => {
    expect(parsePaise(input)).toBe(expected);
  });

  it.each([
    "",
    " ",
    "1.005",
    "-1",
    "+1",
    "1e3",
    "abc",
    "1.2.3",
    "1,2,3",
    "12,34",
    "1,23,45,6",
    ".5",
    "1,000,00",
    "₹",
    "1000000000.01",
    "99999999999999",
  ])("refuses %j", (input) => {
    expect(parsePaise(input)).toBeNull();
  });
});

describe("formatPaise and paiseInput", () => {
  it.each([
    [0, "₹0.00"],
    [5, "₹0.05"],
    [12_500_050, "₹1,25,000.50"],
    [31_850_000, "₹3,18,500.00"],
    [MAX_AMOUNT_MINOR, "₹1,00,00,00,000.00"],
    [-150, "-₹1.50"],
  ])("formats %d paise as %s", (paise, text) => {
    expect(formatPaise(paise)).toBe(text);
  });

  it("round-trips through the editable text", () => {
    for (const paise of [
      0,
      1,
      99,
      100,
      12_500_050,
      31_850_000,
      MAX_AMOUNT_MINOR,
    ]) {
      expect(parsePaise(paiseInput(paise))).toBe(paise);
    }
    expect(paiseInput(12_500_050)).toBe("125000.50");
    expect(paiseInput(25_000_000)).toBe("250000");
  });
});
