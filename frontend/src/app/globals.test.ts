import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// Global accessibility base layer (T00-10). jsdom does not apply this CSS, so
// the rules are pinned here and verified visually in Chromium.

const css = readFileSync(
  path.join(path.dirname(fileURLToPath(import.meta.url)), "globals.css"),
  "utf8",
);
const base = css.slice(css.indexOf("@layer base"));

describe("global accessibility base layer", () => {
  it("gives every unstyled keyboard-focused element the token focus ring", () => {
    const rule = base.slice(base.indexOf(":focus-visible {"));
    expect(rule).toMatch(
      /outline:\s*var\(--focus-ring-width\)\s+solid\s+var\(--focus-ring\);/,
    );
    expect(rule).toMatch(/outline-offset:\s*var\(--focus-ring-offset\);/);
  });

  it("stops non-essential motion when the user prefers reduced motion", () => {
    const block = base.slice(
      base.indexOf("@media (prefers-reduced-motion: reduce)"),
    );
    expect(block).not.toBe("");
    for (const property of [
      "animation-duration",
      "animation-iteration-count",
      "transition-duration",
      "scroll-behavior",
    ]) {
      expect(block).toContain(property);
    }
  });

  it("lives in the base layer, so component utilities still win", () => {
    expect(base.startsWith("@layer base")).toBe(true);
    expect(css.indexOf(":focus-visible")).toBeGreaterThan(
      css.indexOf("@layer base"),
    );
  });
});

describe("print views (Phase 02-5)", () => {
  const block = base.slice(base.indexOf("@media print"));

  it("prints only the marked region and leaves out marked controls", () => {
    expect(block).not.toBe("");
    expect(block).toContain(":where(body:has([data-print-region])) *");
    expect(block).toMatch(/\[data-print-hide\]\s*{\s*display:\s*none/);
  });

  it("lets the region's visibility outrank the hide-everything rule (V-02)", () => {
    // Same layer, so specificity decides. Unwrapped, body:has([attr]) * is
    // (0,1,1) and beats [data-print-region] * at (0,1,0): a blank page.
    // :where() makes the hide rule (0,0,0). Real print output is checked in
    // Chromium (PDF), not here.
    const hide = block.match(/([^{}]+)\{\s*visibility:\s*hidden;/);
    expect(hide?.[1]?.trim()).toMatch(/^:where\([^]*\)\s+\*$/);
    const show = block.match(/([^{}]+)\{\s*visibility:\s*visible;/);
    expect(
      show?.[1]
        ?.split(",")
        .map((s) => s.trim())
        .sort(),
    ).toEqual(["[data-print-region]", "[data-print-region] *"]);
  });

  it("prints on paper, not the Dark page background (V-02)", () => {
    expect(block).toMatch(
      /html:has\(\[data-print-region\]\),\s*html:has\(\[data-print-region\]\) body\s*{\s*background-color:\s*var\(--white\);/,
    );
  });

  it("prints in the Light theme's ink, from tokens only", () => {
    const region = block.slice(block.indexOf("[data-print-region] {"));
    expect(region).toContain("--text-primary: var(--ocean-900);");
    expect(region).toContain("--text-secondary: var(--ink-700);");
    expect(region).toContain("--border-subtle: var(--pearl-200);");
    expect(block).not.toMatch(/#[0-9a-f]{3,8}|rgb\(/i);
  });
});
