import { afterEach, describe, expect, it } from "vitest";

import { THEME_PRE_PAINT_SCRIPT } from "./pre-paint";
import {
  blockLocalStorage,
  installColorScheme,
  removeColorScheme,
  resetDocumentTheme,
} from "./test-helpers";
import { THEME_STORAGE_KEY } from "./theme";

// Executes the exact inline script that the root layout ships.
function runPrePaint() {
  // eslint-disable-next-line @typescript-eslint/no-implied-eval -- test executes the shipped static constant
  const script = new Function(THEME_PRE_PAINT_SCRIPT) as () => void;
  script();
}

const root = document.documentElement;

afterEach(() => {
  window.localStorage.clear();
  removeColorScheme();
  resetDocumentTheme();
});

describe("theme pre-paint script", () => {
  it.each([
    ["light", false, "light"],
    ["light", true, "light"],
    ["dark", false, "dark"],
    ["dark", true, "dark"],
    ["system", false, "light"],
    ["system", true, "dark"],
    [null, true, "dark"],
    [null, false, "light"],
    ["DARK", true, "dark"],
    ['"><img src=x onerror=alert(1)>', false, "light"],
  ] as const)(
    "stored %j with OS dark=%s applies %s before paint",
    (stored, osDark, expected) => {
      installColorScheme(osDark);
      if (stored !== null)
        window.localStorage.setItem(THEME_STORAGE_KEY, stored);

      runPrePaint();

      expect(root.getAttribute("data-theme")).toBe(expected);
      expect(root.style.colorScheme).toBe(expected);
    },
  );

  it("falls back to System when storage is unavailable", () => {
    installColorScheme(true);
    const restore = blockLocalStorage();
    try {
      expect(runPrePaint).not.toThrow();
      expect(root.getAttribute("data-theme")).toBe("dark");
    } finally {
      restore();
    }
  });

  it("applies Light when matchMedia is unavailable and never throws", () => {
    removeColorScheme();
    expect(runPrePaint).not.toThrow();
    expect(root.getAttribute("data-theme")).toBe("light");
  });

  it("is a small static script with no interpolation placeholders", () => {
    expect(THEME_PRE_PAINT_SCRIPT.length).toBeLessThan(1024);
    expect(THEME_PRE_PAINT_SCRIPT).not.toContain("${");
    expect(THEME_PRE_PAINT_SCRIPT).not.toMatch(/<\/?script/i);
    expect(THEME_PRE_PAINT_SCRIPT).toContain(`"${THEME_STORAGE_KEY}"`);
  });
});
