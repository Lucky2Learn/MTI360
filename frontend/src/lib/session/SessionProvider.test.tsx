import { act, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, SessionRefreshedError } from "@/lib/api/errors";
import type { SessionWire } from "@/lib/api/types";
import { apiError, installFetch, ok } from "@/test/fetch-mock";
import {
  CAMPUSES,
  INSTITUTES,
  readySession,
  sessionIn,
} from "@/test/session-fixtures";

import {
  SessionSync,
  TenantSessionProvider,
  useTenantSession,
  type TenantSessionValue,
} from "./SessionProvider";

// Tenant session context (T01-09A): the T01-05 §11 matrix, the T01-08
// suspended / revoked membership flow, visibility re-reads, and no authority
// kept anywhere but the server's latest answer.

const documentNav = vi.hoisted(() => ({
  assignLocation: vi.fn<(url: string) => void>(),
  reloadDocument: vi.fn(),
  currentPath: vi.fn(() => "/app/administration/campuses"),
}));
vi.mock("./document", () => documentNav);

// The latest context value, captured after each render for the assertions.
let context: TenantSessionValue;
function Probe() {
  const value = useTenantSession();
  useEffect(() => {
    context = value;
  });
  return (
    <p data-testid="probe">
      {[...value.session.permissions].join(",")}|
      {value.session.activeCampus?.name ?? "all"}|
      {String(value.changedElsewhere)}
    </p>
  );
}

function renderProvider(session: SessionWire = readySession()) {
  return render(
    <TenantSessionProvider initialSession={session}>
      <Probe />
    </TenantSessionProvider>,
  );
}

const setVisibility = (state: DocumentVisibilityState) => {
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => state,
  });
  document.dispatchEvent(new Event("visibilitychange"));
};

beforeEach(() => {
  documentNav.assignLocation.mockReset();
  documentNav.currentPath.mockReturnValue("/app/administration/campuses");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("401 AUTHENTICATION_REQUIRED (page load or action)", () => {
  it("re-reads the session; none → /session-ended with next (J10)", async () => {
    const api = installFetch();
    api.on("GET /members", apiError(401, "AUTHENTICATION_REQUIRED"));
    api.on("GET /session", apiError(401, "AUTHENTICATION_REQUIRED"));
    renderProvider();
    await expect(context.request("/members")).rejects.toBeInstanceOf(ApiError);
    expect(documentNav.assignLocation).toHaveBeenCalledWith(
      "/session-ended?reason=ended&next=%2Fapp%2Fadministration%2Fcampuses",
    );
  });

  it.each(["SUSPENDED", "REVOKED"])(
    "membership %s: the re-read has no institute → /select-institute",
    async () => {
      const api = installFetch();
      api.on(
        "POST /members/x/invitation/resend",
        apiError(401, "AUTHENTICATION_REQUIRED"),
      );
      api.on("GET /session", ok(sessionIn("institute_selection_required")));
      renderProvider();
      await expect(
        context.request("/members/x/invitation/resend", { method: "POST" }),
      ).rejects.toBeInstanceOf(ApiError);
      expect(documentNav.assignLocation).toHaveBeenCalledWith(
        "/select-institute?next=%2Fapp%2Fadministration%2Fcampuses",
      );
      // The unsafe request was not resent.
      expect(api.callsTo("POST /members/x/invitation/resend")).toHaveLength(1);
    },
  );

  it("no institute left at all → /select-institute (which shows 'No institute available')", async () => {
    const api = installFetch();
    api.on("GET /institute", apiError(401, "AUTHENTICATION_REQUIRED"));
    api.on(
      "GET /session",
      ok(sessionIn("institute_selection_required", { institutes: [] })),
    );
    renderProvider();
    await expect(context.request("/institute")).rejects.toBeInstanceOf(
      ApiError,
    );
    expect(documentNav.assignLocation).toHaveBeenCalledWith(
      "/select-institute?next=%2Fapp%2Fadministration%2Fcampuses",
    );
  });

  it("campus choice required → /select-campus", async () => {
    const api = installFetch();
    api.on("GET /campuses", apiError(401, "AUTHENTICATION_REQUIRED"));
    api.on("GET /session", ok(sessionIn("campus_selection_required")));
    renderProvider();
    await expect(context.request("/campuses")).rejects.toBeInstanceOf(ApiError);
    expect(documentNav.assignLocation).toHaveBeenCalledWith(
      "/select-campus?reason=campus-unavailable&next=%2Fapp%2Fadministration%2Fcampuses",
    );
  });

  it("re-reads once for concurrent 401 responses", async () => {
    const api = installFetch();
    api.on(
      "GET /members",
      apiError(401, "AUTHENTICATION_REQUIRED"),
      apiError(401, "AUTHENTICATION_REQUIRED"),
    );
    api.on("GET /session", apiError(401, "AUTHENTICATION_REQUIRED"));
    renderProvider();
    await Promise.allSettled([
      context.request("/members"),
      context.request("/members"),
    ]);
    expect(api.callsTo("GET /session")).toHaveLength(1);
    expect(documentNav.assignLocation).toHaveBeenCalledTimes(1);
  });
});

describe("403 SESSION_REFRESH_REQUIRED", () => {
  it("GET: re-reads the session and retries ONCE with the fresh CSRF token", async () => {
    const api = installFetch();
    api.on(
      "GET /roles",
      apiError(403, "SESSION_REFRESH_REQUIRED"),
      ok([{ name: "Administrator" }]),
    );
    api.on("GET /session", ok(readySession({ csrf_token: "fresh-csrf" })));
    renderProvider();
    await expect(context.request("/roles")).resolves.toEqual([
      { name: "Administrator" },
    ]);
    expect(api.callsTo("GET /roles")).toHaveLength(2);
  });

  it("GET: a second refusal is not retried again", async () => {
    const api = installFetch();
    api.on(
      "GET /roles",
      apiError(403, "SESSION_REFRESH_REQUIRED"),
      apiError(403, "SESSION_REFRESH_REQUIRED"),
    );
    api.on("GET /session", ok(readySession()));
    renderProvider();
    await expect(context.request("/roles")).rejects.toBeInstanceOf(ApiError);
    expect(api.callsTo("GET /roles")).toHaveLength(2);
  });

  it.each(["POST", "PUT", "PATCH", "DELETE"] as const)(
    "%s: re-reads the session but NEVER resends automatically",
    async (method) => {
      const api = installFetch();
      api.on(`${method} /roles/r1`, apiError(403, "SESSION_REFRESH_REQUIRED"));
      api.on("GET /session", ok(readySession({ csrf_token: "fresh-csrf" })));
      renderProvider();
      await expect(
        context.request("/roles/r1", { method, body: {} }),
      ).rejects.toBeInstanceOf(SessionRefreshedError);
      expect(api.callsTo(`${method} /roles/r1`)).toHaveLength(1);
      expect(api.callsTo("GET /session")).toHaveLength(1);
    },
  );

  it("the user's explicit 'Try again' resends once with the new token", async () => {
    const api = installFetch();
    api.on(
      "POST /members/invitations",
      apiError(403, "SESSION_REFRESH_REQUIRED"),
      ok({}),
    );
    api.on("GET /session", ok(readySession({ csrf_token: "fresh-csrf" })));
    renderProvider();
    await expect(
      context.request("/members/invitations", { method: "POST", body: {} }),
    ).rejects.toBeInstanceOf(SessionRefreshedError);
    await context.request("/members/invitations", { method: "POST", body: {} });
    const [first, second] = api.callsTo("POST /members/invitations");
    expect(first!.headers["x-csrf-token"]).toBe("csrf-token-for-tests-only");
    expect(second!.headers["x-csrf-token"]).toBe("fresh-csrf");
  });

  it("an ended session during the re-read → J10", async () => {
    const api = installFetch();
    api.on("GET /roles", apiError(403, "SESSION_REFRESH_REQUIRED"));
    api.on("GET /session", apiError(401, "AUTHENTICATION_REQUIRED"));
    renderProvider();
    await expect(context.request("/roles")).rejects.toBeInstanceOf(ApiError);
    expect(documentNav.assignLocation).toHaveBeenCalledWith(
      expect.stringMatching(/^\/session-ended\?reason=ended/),
    );
  });
});

describe("403 PERMISSION_DENIED", () => {
  it("is passed to the caller and the session is re-read in the background", async () => {
    const api = installFetch();
    api.on("DELETE /roles/r1", apiError(403, "PERMISSION_DENIED"));
    api.on("GET /session", ok(readySession({ permissions: ["role.read"] })));
    renderProvider(readySession({ permissions: ["role.read", "role.delete"] }));
    const error = await context
      .request("/roles/r1", { method: "DELETE" })
      .catch((caught: unknown) => caught);
    expect((error as ApiError).code).toBe("PERMISSION_DENIED");
    await waitFor(() =>
      expect(screen.getByTestId("probe")).toHaveTextContent(/^role\.read\|/),
    );
    expect(api.callsTo("DELETE /roles/r1")).toHaveLength(1);
  });
});

describe("session state", () => {
  it("uses the CSRF token only from the server session", async () => {
    const api = installFetch();
    api.on("PUT /session/campus", ok(readySession()));
    window.localStorage.setItem("csrf_token", "forged-from-storage");
    renderProvider();
    await context.request("/session/campus", {
      method: "PUT",
      body: { campus_id: null },
    });
    expect(api.calls[0]!.headers["x-csrf-token"]).toBe(
      "csrf-token-for-tests-only",
    );
    window.localStorage.clear();
  });

  it("can() is an exact match over the latest session only", () => {
    renderProvider(readySession({ permissions: ["campus.read"] }));
    expect(context.can("campus.read")).toBe(true);
    expect(context.can("campus.*")).toBe(false);
    expect(context.can("campus")).toBe(false);
    expect(context.can("member.read")).toBe(false);
    expect(context.can("")).toBe(false);
  });

  it("SessionSync replaces the state as a whole on every page navigation", async () => {
    const { rerender } = renderProvider(
      readySession({ permissions: ["campus.read", "member.read"] }),
    );
    rerender(
      <TenantSessionProvider initialSession={readySession()}>
        <SessionSync session={readySession({ permissions: ["audit.read"] })} />
        <Probe />
      </TenantSessionProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("probe")).toHaveTextContent(/^audit\.read\|/),
    );
  });

  it("never writes to browser storage", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const api = installFetch();
    api.on("GET /session", ok(readySession({ permissions: ["role.read"] })));
    renderProvider();
    await act(() => context.refresh());
    expect(setItem).not.toHaveBeenCalled();
  });
});

describe("tab visibility (other tabs)", () => {
  it("re-reads the session when the tab becomes visible and updates permissions", async () => {
    const api = installFetch();
    api.on("GET /session", ok(readySession({ permissions: ["audit.read"] })));
    renderProvider(readySession({ permissions: ["campus.read"] }));
    act(() => setVisibility("visible"));
    await waitFor(() =>
      expect(screen.getByTestId("probe")).toHaveTextContent(/^audit\.read\|/),
    );
  });

  it("does nothing while hidden (no polling)", () => {
    const api = installFetch();
    renderProvider();
    act(() => setVisibility("hidden"));
    expect(api.calls).toHaveLength(0);
  });

  it("session ended in another tab → J10", async () => {
    const api = installFetch();
    api.on("GET /session", apiError(401, "AUTHENTICATION_REQUIRED"));
    renderProvider();
    act(() => setVisibility("visible"));
    await waitFor(() =>
      expect(documentNav.assignLocation).toHaveBeenCalledWith(
        expect.stringMatching(/^\/session-ended\?reason=ended/),
      ),
    );
  });

  it("campus withdrawn → /select-campus", async () => {
    const api = installFetch();
    api.on("GET /session", ok(sessionIn("campus_selection_required")));
    renderProvider();
    act(() => setVisibility("visible"));
    await waitFor(() =>
      expect(documentNav.assignLocation).toHaveBeenCalledWith(
        expect.stringMatching(/^\/select-campus\?/),
      ),
    );
  });

  it("another institute or campus was chosen elsewhere → notice, state kept", async () => {
    const api = installFetch();
    api.on(
      "GET /session",
      ok(
        readySession({
          active_institute: INSTITUTES.harbour,
          institutes: [INSTITUTES.coastal, INSTITUTES.harbour],
          active_campus: CAMPUSES.vizag,
        }),
      ),
    );
    renderProvider();
    act(() => setVisibility("visible"));
    await waitFor(() =>
      expect(screen.getByTestId("probe")).toHaveTextContent(/\|true$/),
    );
    expect(context.session.activeInstitute?.name).toBe(
      "Coastal Maritime Training Institute",
    );
    expect(documentNav.assignLocation).not.toHaveBeenCalled();
  });
});

describe("sign out", () => {
  it("posts /auth/logout and leaves with a full navigation even when it fails", async () => {
    const api = installFetch();
    api.on("POST /auth/logout", new TypeError("offline"));
    renderProvider();
    await act(() => context.signOut());
    expect(api.callsTo("POST /auth/logout")).toHaveLength(1);
    expect(documentNav.assignLocation).toHaveBeenCalledWith(
      "/session-ended?reason=signed-out",
    );
  });
});
