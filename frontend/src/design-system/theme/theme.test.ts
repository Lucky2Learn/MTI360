import { afterEach, describe, expect, it } from "vitest";

import {
  blockLocalStorage,
  installColorScheme,
  removeColorScheme,
  resetDocumentTheme,
} from "./test-helpers";
import {
  applyTheme,
  parseThemePreference,
  readThemePreference,
  resolveTheme,
  systemPrefersDark,
  THEME_STORAGE_KEY,
  writeThemePreference,
} from "./theme";

afterEach(() => {
  window.localStorage.clear();
  removeColorScheme();
  resetDocumentTheme();
});

describe("parseThemePreference", () => {
  it.each(["light", "dark", "system"])("accepts %s", (value) => {
    expect(parseThemePreference(value)).toBe(value);
  });

  it.each([null, undefined, "", "DARK", "blue", 1, {}, "system "])(
    "falls back to system for %j",
    (value) => {
      expect(parseThemePreference(value)).toBe("system");
    },
  );
});

describe("resolveTheme", () => {
  it.each([
    ["light", false, "light"],
    ["light", true, "light"],
    ["dark", false, "dark"],
    ["dark", true, "dark"],
    ["system", false, "light"],
    ["system", true, "dark"],
  ] as const)("%s with OS dark=%s → %s", (preference, osDark, expected) => {
    expect(resolveTheme(preference, osDark)).toBe(expected);
  });
});

describe("preference storage", () => {
  it("defaults to system when nothing is stored", () => {
    expect(readThemePreference()).toBe("system");
  });

  it("persists under the mti360.theme key", () => {
    expect(writeThemePreference("dark")).toBe(true);
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(readThemePreference()).toBe("dark");
  });

  it("ignores an invalid stored value", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "<script>");
    expect(readThemePreference()).toBe("system");
  });

  it("keeps working in memory when storage is unavailable", () => {
    const restore = blockLocalStorage();
    try {
      expect(() => readThemePreference()).not.toThrow();
      expect(writeThemePreference("light")).toBe(false);
      expect(readThemePreference()).toBe("light");
    } finally {
      restore();
    }
  });
});

describe("system colour scheme", () => {
  it("is light when matchMedia is unavailable", () => {
    removeColorScheme();
    expect(systemPrefersDark()).toBe(false);
  });

  it("follows prefers-color-scheme", () => {
    const scheme = installColorScheme(true);
    expect(systemPrefersDark()).toBe(true);
    scheme.setDark(false);
    expect(systemPrefersDark()).toBe(false);
  });
});

describe("applyTheme", () => {
  it("sets data-theme and color-scheme on <html>", () => {
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
  });
});
