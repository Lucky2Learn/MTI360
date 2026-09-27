import {
  DARK_SCHEME_QUERY,
  DEFAULT_THEME_PREFERENCE,
  THEME_PREFERENCES,
  THEME_STORAGE_KEY,
} from "./theme";

// Inline <head> script that applies the theme BEFORE first paint, so there is
// no Light → Dark flash on load (repository-structure.md §2).
//
// Security: a static constant built only from the constants above — no user,
// tenant, URL or request data is ever interpolated. It reads one allow-listed
// localStorage value and never throws. When a Content-Security-Policy is
// introduced (src/proxy.ts), this script must receive the request nonce.
//
// Keep it in sync with theme.ts (parseThemePreference / resolveTheme / applyTheme);
// pre-paint.test.ts executes it against the same cases.

const allowed = JSON.stringify(THEME_PREFERENCES);

export const THEME_PRE_PAINT_SCRIPT = `(function(){try{var p=null;try{p=window.localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)})}catch(e){}if(${allowed}.indexOf(p)<0){p=${JSON.stringify(DEFAULT_THEME_PREFERENCE)}}var d=p==="dark"||(p==="system"&&typeof window.matchMedia==="function"&&window.matchMedia(${JSON.stringify(DARK_SCHEME_QUERY)}).matches);var t=d?"dark":"light";var r=document.documentElement;r.setAttribute("data-theme",t);r.style.colorScheme=t}catch(e){}})();`;
