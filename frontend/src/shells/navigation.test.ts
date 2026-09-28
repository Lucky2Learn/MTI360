import { describe, expect, it } from "vitest";

import {
  findTrail,
  flattenNavigation,
  isCurrentPage,
  normalizePath,
} from "./navigation";
import { TEST_NAVIGATION } from "./test-helpers";

const ids = (pathname: string) =>
  findTrail(TEST_NAVIGATION, pathname).map((item) => item.id);

describe("navigation model", () => {
  it("normalizes trailing slashes but keeps the root", () => {
    expect(normalizePath("/app/")).toBe("/app");
    expect(normalizePath("/")).toBe("/");
  });

  it("finds the trail to an exact page, including its parent", () => {
    expect(ids("/app/admissions/leads")).toEqual(["admissions", "leads"]);
    expect(ids("/app/finance")).toEqual(["finance"]);
    expect(ids("/app")).toEqual(["home"]);
  });

  it("attributes deeper, unlisted paths to the closest listed page", () => {
    expect(ids("/app/admissions/leads/lead-42")).toEqual([
      "admissions",
      "leads",
    ]);
  });

  it("matches on path segments, not string prefixes", () => {
    expect(ids("/app/financeteam")).toEqual(["home"]);
    expect(ids("/platform")).toEqual([]);
  });

  it("identifies the current page exactly", () => {
    const [home] = flattenNavigation(TEST_NAVIGATION);
    expect(isCurrentPage(home!, "/app/")).toBe(true);
    expect(isCurrentPage(home!, "/app/finance")).toBe(false);
  });

  it("flattens nested items in navigation order", () => {
    expect(flattenNavigation(TEST_NAVIGATION).map((item) => item.id)).toEqual([
      "home",
      "admissions",
      "leads",
      "applications",
      "academics",
      "courses",
      "finance",
    ]);
  });
});
