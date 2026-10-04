"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  apiRequest,
  SAFE_METHODS,
  type ApiRequestOptions,
} from "@/lib/api/client";
import { ApiError, SessionRefreshedError } from "@/lib/api/errors";
import type { SessionWire } from "@/lib/api/types";
import { can as canWith } from "@/lib/authz/requirements";

import { readSession, signOut as signOutRequest } from "./client";
import { assignLocation, currentPath } from "./document";
import {
  AUTH_ROUTES,
  authUrl,
  CAMPUS_UNAVAILABLE_REASON,
  sessionEndedUrl,
} from "./routes";
import { toSession, type Session } from "./session";

// Tenant session context (T01-05 UI contract §12; T01-04 §8.8). Provided by
// the /app layout from the server session read and replaced as a whole on
// every re-read. It is NOT a security authority: it only tells the UI what to
// show. It never persists anything and never reads authority from storage or
// the URL.
//
// Re-reads (never polling, §10): every page navigation (the page passes its
// fresh server read to SessionSync), tab visibility, after 403
// PERMISSION_DENIED and 403 SESSION_REFRESH_REQUIRED, and on 401.
//
// `request` applies the §11 matrix to every tenant API call:
// - 401: re-read the session → no session: /session-ended (J10); no institute
//   (membership suspended or revoked, T01-08): /select-institute; campus
//   choice required: /select-campus. Full document navigation.
// - 403 SESSION_REFRESH_REQUIRED: re-read (fresh CSRF token); a GET is retried
//   ONCE; an unsafe request is NEVER resent automatically
//   (SessionRefreshedError → the UI offers "Try again").
// - 403 PERMISSION_DENIED: background re-read; the caller shows AUTHZ-01 or
//   RESOURCE-01.

export type TenantSessionValue = {
  session: Session;
  /** Advisory permission check over the current session (exact match). */
  can: (code: string) => boolean;
  /** Re-reads GET /session. Null when the session ended (navigation started). */
  refresh: () => Promise<Session | null>;
  /** Replaces the state with a server response (switches, SessionSync). */
  replace: (wire: SessionWire) => Session;
  request: <T>(path: `/${string}`, options?: ApiRequestOptions) => Promise<T>;
  /** Increments when page data must be re-fetched (campus switch, D04 rule 9). */
  dataVersion: number;
  invalidate: () => void;
  /** Another tab switched institute or campus (§8.8 "Other tabs"). */
  changedElsewhere: boolean;
  signOut: () => Promise<void>;
};

const TenantSessionContext = createContext<TenantSessionValue | null>(null);

export function useTenantSession(): TenantSessionValue {
  const value = useContext(TenantSessionContext);
  if (!value) {
    throw new Error(
      "useTenantSession must be used inside TenantSessionProvider",
    );
  }
  return value;
}

/** For components that may render outside the tenant shell. */
export function useOptionalTenantSession(): TenantSessionValue | null {
  return useContext(TenantSessionContext);
}

export type TenantSessionProviderProps = {
  initialSession: SessionWire;
  children: ReactNode;
};

export function TenantSessionProvider({
  initialSession,
  children,
}: TenantSessionProviderProps) {
  const [session, setSession] = useState(() => toSession(initialSession));
  const [dataVersion, setDataVersion] = useState(0);
  const [changedElsewhere, setChangedElsewhere] = useState(false);
  const sessionRef = useRef(session);
  const leavingRef = useRef(false);
  const unauthorizedRef = useRef<Promise<Session | null> | null>(null);

  const commit = useCallback((next: Session) => {
    sessionRef.current = next;
    setSession(next);
    return next;
  }, []);

  const leave = useCallback((url: string) => {
    if (leavingRef.current) return;
    leavingRef.current = true;
    assignLocation(url);
  }, []);

  /** Routes a re-read session per §11 (401 row); returns it when usable. */
  const route = useCallback(
    (fresh: Session | null): Session | null => {
      const path = currentPath();
      if (!fresh) {
        leave(sessionEndedUrl(path));
        return null;
      }
      if (!fresh.activeInstitute) {
        leave(authUrl(AUTH_ROUTES.selectInstitute, { next: path }));
        return null;
      }
      if (fresh.campusSelectionRequired) {
        leave(
          authUrl(AUTH_ROUTES.selectCampus, {
            next: path,
            reason: CAMPUS_UNAVAILABLE_REASON,
          }),
        );
        return null;
      }
      return commit(fresh);
    },
    [commit, leave],
  );

  const refresh = useCallback(async () => route(await readSession()), [route]);

  // Stable: SessionSync depends on it.
  const replace = useCallback(
    (wire: SessionWire) => commit(toSession(wire)),
    [commit],
  );
  const invalidate = useCallback(
    () => setDataVersion((version) => version + 1),
    [],
  );
  const signOut = useCallback(() => {
    leavingRef.current = true;
    return signOutRequest();
  }, []);

  // One re-read for any number of concurrent 401 responses.
  const handleUnauthorized = useCallback(() => {
    unauthorizedRef.current ??= refresh().finally(() => {
      unauthorizedRef.current = null;
    });
    return unauthorizedRef.current;
  }, [refresh]);

  const request = useCallback(
    async <T,>(
      path: `/${string}`,
      options: ApiRequestOptions = {},
    ): Promise<T> => {
      const method = options.method ?? "GET";
      const send = (csrfToken: string) =>
        apiRequest<T>(path, { ...options, csrfToken });
      try {
        return await send(sessionRef.current.csrfToken);
      } catch (error) {
        if (!(error instanceof ApiError)) throw error;
        if (error.status === 401) {
          await handleUnauthorized();
          throw error;
        }
        if (error.code === "SESSION_REFRESH_REQUIRED") {
          const fresh = await refresh();
          if (!fresh) throw error;
          if (!SAFE_METHODS.has(method)) throw new SessionRefreshedError();
          try {
            return await send(fresh.csrfToken);
          } catch (retryError) {
            if (retryError instanceof ApiError && retryError.status === 401) {
              await handleUnauthorized();
            }
            throw retryError;
          }
        }
        if (error.code === "PERMISSION_DENIED") {
          void refresh().catch(() => undefined);
        }
        throw error;
      }
    },
    [handleUnauthorized, refresh],
  );

  // Other tabs (§8.8): re-read when the tab becomes visible again.
  useEffect(() => {
    const onVisibilityChange = async () => {
      if (document.visibilityState !== "visible" || leavingRef.current) return;
      let fresh: Session | null;
      try {
        fresh = await readSession();
      } catch {
        return; // Offline or API error: the next request handles it.
      }
      const current = sessionRef.current;
      if (
        fresh?.activeInstitute &&
        !fresh.campusSelectionRequired &&
        (fresh.activeInstitute.id !== current.activeInstitute?.id ||
          (fresh.activeCampus?.id ?? null) !==
            (current.activeCampus?.id ?? null))
      ) {
        setChangedElsewhere(true);
        return;
      }
      route(fresh);
    };
    const listener = () => void onVisibilityChange();
    document.addEventListener("visibilitychange", listener);
    return () => document.removeEventListener("visibilitychange", listener);
  }, [route]);

  const value = useMemo<TenantSessionValue>(
    () => ({
      session,
      can: (code) => canWith(session.permissions, code),
      refresh,
      replace,
      request,
      dataVersion,
      invalidate,
      changedElsewhere,
      signOut,
    }),
    [
      session,
      refresh,
      replace,
      request,
      dataVersion,
      invalidate,
      changedElsewhere,
      signOut,
    ],
  );

  return (
    <TenantSessionContext.Provider value={value}>
      {children}
    </TenantSessionContext.Provider>
  );
}

/**
 * Hands a page's fresh server session read to the provider, so navigation,
 * actions and the roles line follow permission changes on every page
 * navigation (T01-05 §10 item 1). Renders nothing; does nothing outside
 * the provider.
 */
export function SessionSync({ session }: { session: SessionWire }) {
  const replace = useOptionalTenantSession()?.replace;
  const serialized = JSON.stringify(session);
  useEffect(() => {
    replace?.(JSON.parse(serialized) as SessionWire);
  }, [replace, serialized]);
  return null;
}
