import { describe, expect, it } from "vitest";

import { nextQuery } from "./list-params";

// URL list state (Phase 02-1; blueprint §23): filters replace their key,
// empty values are removed, and changing a filter returns to page one.

describe("nextQuery", () => {
  const current = new URLSearchParams(
    "view=board&status=NEW&owner=me&offset=50",
  );

  it("replaces a key and resets the page", () => {
    expect(nextQuery(current, { status: "LOST" })).toBe(
      "view=board&owner=me&status=LOST",
    );
  });

  it("removes keys set to null or an empty string", () => {
    expect(nextQuery(current, { owner: null, status: "" })).toBe("view=board");
  });

  it("supports repeated keys and keeping the page", () => {
    expect(nextQuery(current, { status: ["NEW", "CONTACTED"] }, true)).toBe(
      "view=board&owner=me&offset=50&status=NEW&status=CONTACTED",
    );
  });
});
