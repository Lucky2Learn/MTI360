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
import {
  ApiError,
  SessionRefreshedError,
  StepUpCancelledError,
  StepUpFailedError,
} from "@/lib/api/errors";
import type { PlatformSessionWire } from "@/lib/api/types";
import { can as canWith } from "@/lib/authz/requirements";

import { assignLocation, currentPath } from "./document";
import { readPlatformSessionClient, signOutPlatform } from "./platform-client";
import { platformSessionEndedUrl } from "./platform-routes";
import { toPlatformSession, type PlatformSession } from "./platform-session";

// Platform session context (T01-09B UI contract §8, §9). Provided by the
// platform console layout from the server session read and replaced as a
// whole on every re-read. NOT a security authority: it only tells the UI
// what to show; it never persists anything or reads authority from storage
// or the URL. Paths passed to `request` are relative to /api/v1/platform.
//
// Re-reads (never polling, no idle timer — D9B-12): every page navigation
// (PlatformSessionSync), tab visibility, after 403 PERMISSION_DENIED and
// SESSION_REFRESH_REQUIRED, and on 401.
//
// `request` applies the T01-05 §11 matrix plus step-up:
// - 401: re-read → no session: /platform/session-ended (full navigation);
// - 403 SESSION_REFRESH_REQUIRED: re-read (fresh CSRF); a GET is retried
//   ONCE; an unsafe request is NEVER resent (SessionRefreshedError);
// - 403 PERMISSION_DENIED: background re-read;
// - 403 STEP_UP_REQUIRED: open the step-up dialog (PAUTH-07). On success the
//   original request is resent EXACTLY ONCE — safe because the backend
//   raises STEP_UP_REQUIRED before the protected handler runs (D9B-6). A
//   second STEP_UP_REQUIRED → StepUpFailedError (no loop); cancel →
//   StepUpCancelledError (nothing performed). The browser clock never
//   decides anything.

export type PlatformSessionValue = {
  session: PlatformSession;
  /** Advisory permission check over the current session (exact match). */
  can: (code: string) => boolean;
  /** Re-reads GET /platform/session. Null when the session ended. */
  refresh: () => Promise<PlatformSession | null>;
  /** Replaces the state with a full-session server response. */
  replace: (wire: PlatformSessionWire) => PlatformSession | null;
  request: <T>(path: `/${string}`, options?: ApiRequestOptions) => Promise<T>;
  /** One 401 handling for any number of callers (navigates when ended). */
  handleUnauthorized: () => Promise<PlatformSession | null>;
  /** Step-up dialog state (PAUTH-07). */
  stepUpOpen: boolean;
  /** The dialog verified a code: the session response of /session/step-up. */
  completeStepUp: (wire: PlatformSessionWire) => void;
  cancelStepUp: () => void;
  signOut: () => Promise<void>;
};

const PlatformSessionContext = createContext<PlatformSessionValue | null>(null);

export function usePlatformSession(): PlatformSessionValue {
  const value = useContext(PlatformSessionContext);
  if (!value) {
    throw new Error(
      "usePlatformSession must be used inside PlatformSessionProvider",
    );
  }
  return value;
}

export function useOptionalPlatformSession(): PlatformSessionValue | null {
  return useContext(PlatformSessionContext);
}

const PLATFORM_PREFIX = "/platform";

export type PlatformSessionProviderProps = {
  initialSession: PlatformSessionWire;
  children: ReactNode;
};

export function PlatformSessionProvider({
  initialSession,
  children,
}: PlatformSessionProviderProps) {
  // The layout only passes a full session (readPlatformSession).
  const [session, setSession] = useState(() =>
    toPlatformSession(initialSession)!,
  );
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const sessionRef = useRef(session);
  const leavingRef = useRef(false);
  const unauthorizedRef = useRef<Promise<PlatformSession | null> | null>(null);
  const stepUpRef = useRef<{
    promise: Promise<boolean>;
    settle: (verified: boolean) => void;
  } | null>(null);

  const commit = useCallback((next: PlatformSession) => {
    sessionRef.current = next;
    setSession(next);
    return next;
  }, []);

  const leave = useCallback((url: string) => {
    if (leavingRef.current) return;
    leavingRef.current = true;
    assignLocation(url);
  }, []);

  const route = useCallback(
    (fresh: PlatformSession | null): PlatformSession | null => {
      if (!fresh) {
        leave(platformSessionEndedUrl(currentPath()));
        return null;
      }
      return commit(fresh);
    },
    [commit, leave],
  );

  const refresh = useCallback(
    async () => route(await readPlatformSessionClient()),
    [route],
  );

  const replace = useCallback(
    (wire: PlatformSessionWire) => {
      const next = toPlatformSession(wire);
      return next ? commit(next) : null;
    },
    [commit],
  );

  const handleUnauthorized = useCallback(() => {
    unauthorizedRef.current ??= refresh().finally(() => {
      unauthorizedRef.current = null;
    });
    return unauthorizedRef.current;
  }, [refresh]);

  /** Opens the dialog once for any number of concurrent refusals. */
  const awaitStepUp = useCallback((): Promise<boolean> => {
    if (!stepUpRef.current) {
      let settle: (verified: boolean) => void = () => undefined;
      const promise = new Promise<boolean>((resolve) => {
        settle = resolve;
      });
      stepUpRef.current = { promise, settle };
      setStepUpOpen(true);
    }
    return stepUpRef.current.promise;
  }, []);

  const finishStepUp = useCallback((verified: boolean) => {
    const pending = stepUpRef.current;
    stepUpRef.current = null;
    setStepUpOpen(false);
    pending?.settle(verified);
  }, []);

  const completeStepUp = useCallback(
    (wire: PlatformSessionWire) => {
      replace(wire);
      finishStepUp(true);
    },
    [finishStepUp, replace],
  );

  const cancelStepUp = useCallback(() => finishStepUp(false), [finishStepUp]);

  const signOut = useCallback(() => {
    leavingRef.current = true;
    return signOutPlatform();
  }, []);

  const request = useCallback(
    async <T,>(
      path: `/${string}`,
      options: ApiRequestOptions = {},
    ): Promise<T> => {
      const method = options.method ?? "GET";
      const send = () =>
        apiRequest<T>(`${PLATFORM_PREFIX}${path}`, {
          ...options,
          csrfToken: sessionRef.current.csrfToken,
        });
      /** 401 on any attempt ends the session; everything else is rethrown. */
      const settled = async (attempt: () => Promise<T>): Promise<T> => {
        try {
          return await attempt();
        } catch (error) {
          if (error instanceof ApiError && error.status === 401) {
            await handleUnauthorized();
          }
          throw error;
        }
      };

      try {
        return await send();
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
          return settled(send);
        }
        if (error.code === "STEP_UP_REQUIRED") {
          if (!(await awaitStepUp())) throw new StepUpCancelledError();
          return settled(async () => {
            try {
              return await send();
            } catch (retryError) {
              if (
                retryError instanceof ApiError &&
                retryError.code === "STEP_UP_REQUIRED"
              ) {
                throw new StepUpFailedError();
              }
              throw retryError;
            }
          });
        }
        if (error.code === "PERMISSION_DENIED") {
          void refresh().catch(() => undefined);
        }
        throw error;
      }
    },
    [awaitStepUp, handleUnauthorized, refresh],
  );

  // Other tabs: re-read when the tab becomes visible again.
  useEffect(() => {
    const onVisibilityChange = async () => {
      if (document.visibilityState !== "visible" || leavingRef.current) return;
      let fresh: PlatformSession | null;
      try {
        fresh = await readPlatformSessionClient();
      } catch {
        return; // Offline or API error: the next request handles it.
      }
      route(fresh);
    };
    const listener = () => void onVisibilityChange();
    document.addEventListener("visibilitychange", listener);
    return () => document.removeEventListener("visibilitychange", listener);
  }, [route]);

  const value = useMemo<PlatformSessionValue>(
    () => ({
      session,
      can: (code) => canWith(session.permissions, code),
      refresh,
      replace,
      request,
      handleUnauthorized,
      stepUpOpen,
      completeStepUp,
      cancelStepUp,
      signOut,
    }),
    [
      session,
      refresh,
      replace,
      request,
      handleUnauthorized,
      stepUpOpen,
      completeStepUp,
      cancelStepUp,
      signOut,
    ],
  );

  return (
    <PlatformSessionContext.Provider value={value}>
      {children}
    </PlatformSessionContext.Provider>
  );
}

/**
 * Hands a page's fresh server session read to the provider on every page
 * navigation. Renders nothing; does nothing outside the provider.
 */
export function PlatformSessionSync({
  session,
}: {
  session: PlatformSessionWire;
}) {
  const replace = useOptionalPlatformSession()?.replace;
  const serialized = JSON.stringify(session);
  useEffect(() => {
    replace?.(JSON.parse(serialized) as PlatformSessionWire);
  }, [replace, serialized]);
  return null;
}
