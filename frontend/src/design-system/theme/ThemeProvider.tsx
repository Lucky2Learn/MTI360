"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import {
  applyTheme,
  darkSchemeQuery,
  readThemePreference,
  resolveTheme,
  systemPrefersDark,
  THEME_STORAGE_KEY,
  writeThemePreference,
  type ResolvedTheme,
  type ThemePreference,
} from "./theme";

// Theme state is an external store (localStorage + the OS colour scheme), read
// with useSyncExternalStore: the server snapshot is "system", so hydration
// never mismatches, and the client then switches to the stored preference.
// The pre-paint script has already applied the correct theme to <html>.

type Snapshot = `${ThemePreference}|${ResolvedTheme}`;
const SERVER_SNAPSHOT: Snapshot = "system|light";

const localListeners = new Set<() => void>();

function subscribe(onChange: () => void): () => void {
  localListeners.add(onChange);

  // Another tab changed the preference (cross-tab sync).
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === THEME_STORAGE_KEY) onChange();
  };
  window.addEventListener("storage", onStorage);

  // The operating-system colour scheme changed (live System mode).
  const query = darkSchemeQuery();
  query?.addEventListener("change", onChange);

  return () => {
    localListeners.delete(onChange);
    window.removeEventListener("storage", onStorage);
    query?.removeEventListener("change", onChange);
  };
}

function getSnapshot(): Snapshot {
  const preference = readThemePreference();
  return `${preference}|${resolveTheme(preference, systemPrefersDark())}`;
}

function getServerSnapshot(): Snapshot {
  return SERVER_SNAPSHOT;
}

export type ThemeContextValue = {
  /** What the user chose: light, dark or system. */
  preference: ThemePreference;
  /** What is applied: light or dark (System resolved against the OS). */
  resolvedTheme: ResolvedTheme;
  setPreference: (preference: ThemePreference) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const snapshot = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot,
  );
  const [preference, resolvedTheme] = snapshot.split("|") as [
    ThemePreference,
    ResolvedTheme,
  ];

  useEffect(() => {
    applyTheme(resolvedTheme);
  }, [resolvedTheme]);

  const setPreference = useCallback((next: ThemePreference) => {
    writeThemePreference(next);
    localListeners.forEach((listener) => listener());
  }, []);

  const value = useMemo(
    () => ({ preference, resolvedTheme, setPreference }),
    [preference, resolvedTheme, setPreference],
  );

  return <ThemeContext value={value}>{children}</ThemeContext>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within <ThemeProvider>");
  return context;
}
