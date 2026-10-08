"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

// URL list state for T02 Data List pages (Phase 02-1; blueprint §23). Filters,
// sort, page and view live in the URL so lists are bookmarkable and the
// server renders them. Values are IDs and enums only — the one exception is
// the search box term (`q`), which is sent only from the search box and never
// persisted elsewhere. Changing a filter returns to the first page.

export type ListParamValue = string | readonly string[] | null | undefined;

export type ListParams = {
  get: (key: string) => string | null;
  getAll: (key: string) => string[];
  /** Applies `updates` (null/empty removes a key); resets `offset` unless kept. */
  set: (
    updates: Record<string, ListParamValue>,
    options?: { keepPage?: boolean },
  ) => void;
  /** The current query string without the leading "?". */
  query: string;
};

/** Pure: the next query string after `updates`. */
export function nextQuery(
  current: URLSearchParams,
  updates: Record<string, ListParamValue>,
  keepPage = false,
): string {
  const next = new URLSearchParams(current);
  for (const [key, value] of Object.entries(updates)) {
    next.delete(key);
    if (value === null || value === undefined) continue;
    const values = typeof value === "string" ? [value] : value;
    for (const item of values) if (item !== "") next.append(key, item);
  }
  if (!keepPage) next.delete("offset");
  return next.toString();
}

export function useListParams(): ListParams {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const query = params.toString();

  const set = useCallback(
    (
      updates: Record<string, ListParamValue>,
      { keepPage = false }: { keepPage?: boolean } = {},
    ) => {
      const next = nextQuery(new URLSearchParams(query), updates, keepPage);
      router.replace(next ? `${pathname}?${next}` : pathname, {
        scroll: false,
      });
    },
    [pathname, query, router],
  );

  return useMemo(
    () => ({
      get: (key: string) => params.get(key),
      getAll: (key: string) => params.getAll(key),
      set,
      query,
    }),
    [params, query, set],
  );
}
