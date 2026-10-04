"use client";

import { useEffect, useRef, useState } from "react";

import { takeFragmentToken } from "@/lib/session/document";

/**
 * The `#token=` of the current URL, read once after mount and removed from
 * the address bar at once (T01-04 UI contract §6.1). `undefined` until read
 * (server render and first client render), then the token or null.
 *
 * The token lives in a ref and this hook's state only — never in browser
 * storage, a URL, the DOM or a log — and is sent only in POST bodies (S9,
 * S10). The ref keeps it across React's development double effects, which
 * would otherwise find the fragment already removed.
 */
export function useFragmentToken(): string | null | undefined {
  const taken = useRef<string | null | undefined>(undefined);
  const [token, setToken] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    if (taken.current === undefined) taken.current = takeFragmentToken();
    setToken(taken.current);
  }, []);
  return token;
}
