import { describe, expect, it } from "vitest";

import { cx, focusRing } from "./cx";

describe("cx", () => {
  it("joins truthy class names in order", () => {
    expect(cx("a", "b c", "d")).toBe("a b c d");
  });

  it("skips false, null, undefined and empty strings", () => {
    const disabled = false;
    expect(cx("a", disabled && "b", null, undefined, "", "c")).toBe("a c");
  });

  it("returns an empty string for no classes", () => {
    expect(cx()).toBe("");
  });
});

describe("focusRing", () => {
  it("uses the semantic focus-ring colour and component-token width", () => {
    expect(focusRing).toContain("outline-focus-ring");
    expect(focusRing).toContain("outline-(length:--focus-ring-width)");
    expect(focusRing).toContain("outline-offset-(length:--focus-ring-offset)");
  });
});
