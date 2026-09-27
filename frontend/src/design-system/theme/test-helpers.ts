// Test-only helpers for the theme runtime (jsdom has no matchMedia and cannot
// simulate blocked storage).

import { DARK_SCHEME_QUERY } from "./theme";

type Listener = (event: MediaQueryListEvent) => void;

/** Installs a controllable prefers-color-scheme media query on window. */
export function installColorScheme(initiallyDark: boolean) {
  let dark = initiallyDark;
  const listeners = new Set<Listener>();
  const query = {
    get matches() {
      return dark;
    },
    media: DARK_SCHEME_QUERY,
    onchange: null,
    addEventListener: (_type: string, listener: Listener) =>
      listeners.add(listener),
    removeEventListener: (_type: string, listener: Listener) =>
      listeners.delete(listener),
    addListener: (listener: Listener) => listeners.add(listener),
    removeListener: (listener: Listener) => listeners.delete(listener),
    dispatchEvent: () => true,
  };
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (media: string) =>
      media === DARK_SCHEME_QUERY ? query : { ...query, matches: false, media },
  });
  return {
    setDark(value: boolean) {
      dark = value;
      listeners.forEach((listener) =>
        listener({
          matches: value,
          media: DARK_SCHEME_QUERY,
        } as MediaQueryListEvent),
      );
    },
    listenerCount: () => listeners.size,
  };
}

export function removeColorScheme() {
  Reflect.deleteProperty(window, "matchMedia");
}

/** Makes window.localStorage throw on access (privacy mode / blocked storage). */
export function blockLocalStorage(): () => void {
  const own = Object.getOwnPropertyDescriptor(window, "localStorage");
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    get() {
      throw new DOMException("Storage is disabled", "SecurityError");
    },
  });
  return () => {
    if (own) Object.defineProperty(window, "localStorage", own);
    else Reflect.deleteProperty(window, "localStorage");
  };
}

export function resetDocumentTheme() {
  const root = document.documentElement;
  delete root.dataset.theme;
  root.style.colorScheme = "";
}
