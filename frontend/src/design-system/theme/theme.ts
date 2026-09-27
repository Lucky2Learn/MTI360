// Light / Dark / System theme preference (T00-06, DESIGN-SYSTEM.md §11–§15).
//
// The preference is stored locally (decision D9). Per-user persistence for
// authenticated users arrives with identity in Phase 01. Every browser API
// access is guarded: storage can be unavailable (privacy modes, blocked
// cookies) and matchMedia can be missing; the theme then falls back safely.

export const THEME_STORAGE_KEY = "mti360.theme";
export const THEME_PREFERENCES = ["light", "dark", "system"] as const;
export const DEFAULT_THEME_PREFERENCE: ThemePreference = "system";
export const DARK_SCHEME_QUERY = "(prefers-color-scheme: dark)";

export type ThemePreference = (typeof THEME_PREFERENCES)[number];
export type ResolvedTheme = "light" | "dark";

export function isThemePreference(value: unknown): value is ThemePreference {
  return (
    typeof value === "string" &&
    (THEME_PREFERENCES as readonly string[]).includes(value)
  );
}

/** Any unknown or missing value becomes the default preference. */
export function parseThemePreference(value: unknown): ThemePreference {
  return isThemePreference(value) ? value : DEFAULT_THEME_PREFERENCE;
}

export function resolveTheme(
  preference: ThemePreference,
  systemPrefersDark: boolean,
): ResolvedTheme {
  if (preference === "system") return systemPrefersDark ? "dark" : "light";
  return preference;
}

function localStorageOrNull(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null; // accessing window.localStorage itself can throw
  }
}

// Used only while storage is unavailable, so a selection still applies for the
// lifetime of the page.
let memoryPreference: ThemePreference | null = null;

export function readThemePreference(): ThemePreference {
  try {
    const storage = localStorageOrNull();
    if (storage)
      return parseThemePreference(storage.getItem(THEME_STORAGE_KEY));
  } catch {
    // fall through to the in-memory preference
  }
  return memoryPreference ?? DEFAULT_THEME_PREFERENCE;
}

/** Persists the preference; returns false when storage is unavailable. */
export function writeThemePreference(preference: ThemePreference): boolean {
  memoryPreference = preference;
  try {
    const storage = localStorageOrNull();
    if (!storage) return false;
    storage.setItem(THEME_STORAGE_KEY, preference);
    return true;
  } catch {
    return false;
  }
}

export function darkSchemeQuery(): MediaQueryList | null {
  try {
    return typeof window !== "undefined" &&
      typeof window.matchMedia === "function"
      ? window.matchMedia(DARK_SCHEME_QUERY)
      : null;
  } catch {
    return null;
  }
}

export function systemPrefersDark(): boolean {
  return darkSchemeQuery()?.matches ?? false;
}

/** Applies the resolved theme to <html>: semantic tokens switch on data-theme. */
export function applyTheme(
  theme: ResolvedTheme,
  root: HTMLElement = document.documentElement,
): void {
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
}
