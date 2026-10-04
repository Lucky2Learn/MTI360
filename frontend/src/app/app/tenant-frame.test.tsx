import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { toastQueue } from "@/design-system/components";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import {
  installColorScheme,
  removeColorScheme,
} from "@/design-system/theme/test-helpers";
import type { SessionWire } from "@/lib/api/types";
import { apiError, installFetch, noContent, ok } from "@/test/fetch-mock";
import { renderScreen } from "@/test/render-screen";
import { CAMPUSES, INSTITUTES, readySession } from "@/test/session-fixtures";

import { TenantFrame } from "./tenant-frame";

// Whole flows typed key by key through React Aria: allow for a loaded CI host.
vi.setConfig({ testTimeout: 20_000 });

// The /app frame (T01-09A): NAV-01/02 filtering, SESSION-01, the institute
// context, the campus switcher (a view filter, D-B1) and sign-out (J9).

const router = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/app",
  useRouter: () => router,
}));

const navigation = vi.hoisted(() => ({
  assignLocation: vi.fn<(url: string) => void>(),
  reloadDocument: vi.fn(),
  currentPath: vi.fn(() => "/app"),
}));
vi.mock("@/lib/session/document", () => navigation);

const BELOW_TABLET = "(max-width: 47.99rem)";

function renderFrame(session: SessionWire, theme: "light" | "dark" = "light") {
  return renderScreen(
    <TenantFrame session={session} showUnreleased={false}>
      <h1>Dashboard</h1>
    </TenantFrame>,
    { theme },
  );
}

// Every rendered link, including those under a collapsed disclosure:
// items the member may not see are not rendered at all.
const sidebarLinks = () =>
  within(
    screen.getAllByRole("navigation", { name: "Institute navigation" })[0]!,
  )
    .getAllByRole("link", { hidden: true })
    .map((link) => link.textContent?.trim());

async function openAccountMenu(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /account menu$/ }));
  return screen.getByRole("menu");
}

beforeEach(() => {
  navigation.assignLocation.mockReset();
  router.refresh.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
  removeColorScheme();
  for (const item of toastQueue.visibleToasts) toastQueue.close(item.key);
});

describe("permission-aware navigation (NAV-01 / NAV-02)", () => {
  it("with campus.read only: Dashboard and Administration → Campuses", () => {
    renderFrame(readySession({ permissions: ["campus.read"] }));
    expect(sidebarLinks()).toEqual(["Dashboard", "Administration", "Campuses"]);
    const nav = screen.getAllByRole("navigation", {
      name: "Institute navigation",
    })[0]!;
    expect(
      within(nav).getByRole("link", { name: "Administration" }),
    ).toHaveAttribute("href", "/app/administration/campuses");
    expect(within(nav).queryByText("Operations")).toBeNull();
    expect(within(nav).queryByText("Engagement & Intelligence")).toBeNull();
  });

  it("with no permissions: only the Dashboard", () => {
    renderFrame(readySession({ permissions: [] }));
    expect(sidebarLinks()).toEqual(["Dashboard"]);
  });

  it("the mobile drawer shows the same filtered items", async () => {
    renderFrame(readySession({ permissions: ["member.read", "role.read"] }));
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    const drawer = screen.getByRole("dialog");
    expect(
      within(drawer)
        .getAllByRole("link", { hidden: true })
        .map((link) => link.textContent?.trim()),
    ).toEqual(["Dashboard", "Administration", "Users", "Roles"]);
  });

  it("command search finds only visible pages", async () => {
    renderFrame(readySession({ permissions: ["audit.read"] }));
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getAllByRole("button", { name: "Search" })[0]!);
    const dialog = screen.getByRole("dialog", { name: "Search" });
    const search = within(dialog).getByRole("searchbox", {
      name: "Search pages",
    });
    await user.type(search, "Users");
    expect(within(dialog).queryByRole("link", { name: /Users/ })).toBeNull();
    await user.clear(search);
    await user.type(search, "Audit");
    expect(
      within(dialog).getByRole("link", { name: /Audit Logs/ }),
    ).toBeInTheDocument();
  });

  it("updates the navigation when a re-read removes a permission", async () => {
    const api = installFetch();
    api.on("GET /session", ok(readySession({ permissions: [] })));
    renderFrame(readySession({ permissions: ["campus.read"] }));
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "visible",
    });
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await waitFor(() => expect(sidebarLinks()).toEqual(["Dashboard"]));
  });
});

describe("account menu (SESSION-01) and sign out (J9)", () => {
  it("shows the real identity, the institute and the roles line; never codes or IDs", async () => {
    renderFrame(
      readySession({
        permissions: ["member.read"],
        roles: [
          { name: "Institute owner", is_system: true },
          { name: "Admissions Counsellor", is_system: false },
        ],
      }),
    );
    const user = userEvent.setup({ delay: null });
    expect(
      screen.getByRole("button", { name: "Ananya Rao, account menu" }),
    ).toHaveTextContent("AR");
    await openAccountMenu(user);
    const header = screen.getByText(
      "Roles: Institute owner, Admissions Counsellor",
    );
    const panel = header.parentElement!;
    expect(panel).toHaveTextContent("ananya.rao@coastal-maritime.example");
    expect(panel).toHaveTextContent("Coastal Maritime Training Institute");
    expect(document.body.textContent).not.toMatch(
      /member\.read|csrf|7d0c3c2e|Demo account|Institute administrator/,
    );
  });

  it("says when no role is assigned", async () => {
    renderFrame(readySession({ roles: [] }));
    const user = userEvent.setup({ delay: null });
    await openAccountMenu(user);
    expect(
      screen.getByText("No role assigned in this institute"),
    ).toBeInTheDocument();
  });

  it("signs out with a full-page loading state and a full navigation, whatever the answer", async () => {
    const api = installFetch();
    let release!: () => void;
    api.on("POST /auth/logout", noContent());
    api.fetchMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = () => resolve(apiError(500, "INTERNAL_ERROR"));
        }),
    );
    renderFrame(readySession());
    const user = userEvent.setup({ delay: null });
    await openAccountMenu(user);
    await user.click(screen.getByRole("menuitem", { name: "Sign out" }));
    expect(screen.getByText("Signing out")).toBeInTheDocument();
    release();
    await waitFor(() =>
      expect(navigation.assignLocation).toHaveBeenCalledWith(
        "/session-ended?reason=signed-out",
      ),
    );
  });
});

describe("institute context (TenantContext)", () => {
  const twoInstitutes = () =>
    readySession({ institutes: [INSTITUTES.coastal, INSTITUTES.harbour] });

  it("is plain text with one institute", () => {
    renderFrame(readySession());
    expect(screen.queryByRole("button", { name: /^Institute:/ })).toBeNull();
    expect(
      screen.getAllByText("Coastal Maritime Training Institute").length,
    ).toBeGreaterThan(0);
  });

  it("switches through PUT /session/tenant and reloads to /app (next not honoured)", async () => {
    const api = installFetch();
    api.on(
      "PUT /session/tenant",
      ok(readySession({ active_institute: INSTITUTES.harbour })),
    );
    renderFrame(twoInstitutes());
    const user = userEvent.setup({ delay: null });
    await user.click(
      screen.getByRole("button", {
        name: "Institute: Coastal Maritime Training Institute. Switch institute",
      }),
    );
    const dialog = screen.getByRole("dialog", { name: "Switch institute" });
    expect(
      within(dialog).getByRole("radio", { name: /Coastal/ }),
    ).toBeChecked();
    await user.click(within(dialog).getByRole("radio", { name: /Harbour/ }));
    await user.click(within(dialog).getByRole("button", { name: "Switch" }));
    await waitFor(() =>
      expect(navigation.assignLocation).toHaveBeenCalledWith("/app"),
    );
    expect(api.calls[0]).toMatchObject({
      body: { tenant_id: INSTITUTES.harbour.id },
      headers: { "x-csrf-token": "csrf-token-for-tests-only" },
    });
  });

  it("a refused institute (404) stays in the dialog with a warning", async () => {
    const api = installFetch();
    api.on("PUT /session/tenant", apiError(404, "NOT_FOUND"));
    api.on("GET /session", ok(readySession()));
    renderFrame(twoInstitutes());
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("button", { name: /^Institute:/ }));
    const dialog = screen.getByRole("dialog", { name: "Switch institute" });
    await user.click(within(dialog).getByRole("radio", { name: /Harbour/ }));
    await user.click(within(dialog).getByRole("button", { name: "Switch" }));
    expect(
      await within(dialog).findByText(
        "That institute is no longer available to you.",
      ),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        within(dialog).queryByRole("radio", { name: /Harbour/ }),
      ).toBeNull(),
    );
    expect(navigation.assignLocation).not.toHaveBeenCalled();
  });
});

describe("campus switcher (CampusSwitcher, D04, CAMPUS-01)", () => {
  const allScope = () =>
    readySession({
      active_campus: null,
      campus_options: [CAMPUSES.kochi, CAMPUSES.vizag],
      all_campuses_allowed: true,
      permissions: ["campus.read", "member.read"],
    });

  it("is plain text with one campus and absent with none", () => {
    const { unmount } = renderFrame(readySession());
    expect(screen.queryByRole("button", { name: /^Campus:/ })).toBeNull();
    expect(screen.getByText("Kochi Campus")).toBeInTheDocument();
    unmount();
    renderFrame(readySession({ campus_options: [], active_campus: null }));
    expect(screen.queryByText("Kochi Campus")).toBeNull();
  });

  it("offers 'All campuses' first only when allowed, and switches without a reload", async () => {
    const api = installFetch();
    api.on(
      "PUT /session/campus",
      ok({ ...allScope(), active_campus: CAMPUSES.vizag }),
    );
    renderFrame(allScope());
    const user = userEvent.setup({ delay: null });
    await user.click(
      screen.getByRole("button", {
        name: "Campus: All campuses. Switch campus",
      }),
    );
    const dialog = screen.getByRole("dialog", { name: "Switch campus" });
    const radios = within(dialog).getAllByRole("radio");
    expect(radios[0]).toHaveAccessibleName(/All campuses/);
    expect(radios[0]).toBeChecked();
    await user.click(
      within(dialog).getByRole("radio", { name: /Visakhapatnam/ }),
    );
    await user.click(within(dialog).getByRole("button", { name: "Switch" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: "Switch campus" }),
      ).toBeNull(),
    );
    expect(api.calls[0]!.body).toEqual({ campus_id: CAMPUSES.vizag.id });
    // Page data is re-fetched; no document navigation, permissions unchanged.
    expect(router.refresh).toHaveBeenCalled();
    expect(navigation.assignLocation).not.toHaveBeenCalled();
    expect(sidebarLinks()).toEqual([
      "Dashboard",
      "Administration",
      "Campuses",
      "Users",
    ]);
    expect(
      toastQueue.visibleToasts.map((item) => item.content.title),
    ).toContain("Showing Visakhapatnam Campus");
    await waitFor(() =>
      expect(
        screen.getByRole("button", {
          name: "Campus: Visakhapatnam Campus. Switch campus",
        }),
      ).toHaveFocus(),
    );
  });

  it("sends null for 'All campuses'", async () => {
    const api = installFetch();
    api.on("PUT /session/campus", ok(allScope()));
    renderFrame({ ...allScope(), active_campus: CAMPUSES.kochi });
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("button", { name: /^Campus: Kochi/ }));
    const dialog = screen.getByRole("dialog", { name: "Switch campus" });
    await user.click(
      within(dialog).getByRole("radio", { name: /All campuses/ }),
    );
    await user.click(within(dialog).getByRole("button", { name: "Switch" }));
    await waitFor(() => expect(api.calls).toHaveLength(1));
    expect(api.calls[0]!.body).toEqual({ campus_id: null });
  });

  it("never offers 'All campuses' without all_campuses_allowed", async () => {
    renderFrame(
      readySession({
        campus_options: [CAMPUSES.kochi, CAMPUSES.vizag],
        all_campuses_allowed: false,
      }),
    );
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("button", { name: /^Campus: Kochi/ }));
    const dialog = screen.getByRole("dialog", { name: "Switch campus" });
    expect(within(dialog).queryByText("All campuses")).toBeNull();
  });

  it("a withdrawn campus (404): warning in the dialog and the options replaced", async () => {
    const api = installFetch();
    api.on("PUT /session/campus", apiError(404, "NOT_FOUND"));
    api.on(
      "GET /session",
      ok({ ...allScope(), campus_options: [CAMPUSES.kochi] }),
    );
    renderFrame(allScope());
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("button", { name: /^Campus:/ }));
    const dialog = screen.getByRole("dialog", { name: "Switch campus" });
    await user.click(
      within(dialog).getByRole("radio", { name: /Visakhapatnam/ }),
    );
    await user.click(within(dialog).getByRole("button", { name: "Switch" }));
    expect(
      await within(dialog).findByText(
        "That campus is no longer available to you.",
      ),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        within(dialog).queryByRole("radio", { name: /Visakhapatnam/ }),
      ).toBeNull(),
    );
  });

  it("refreshed session (403 SESSION_REFRESH_REQUIRED): asks to try again, does not resend", async () => {
    const api = installFetch();
    api.on("PUT /session/campus", apiError(403, "SESSION_REFRESH_REQUIRED"));
    api.on("GET /session", ok(allScope()));
    renderFrame(allScope());
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("button", { name: /^Campus:/ }));
    const dialog = screen.getByRole("dialog", { name: "Switch campus" });
    await user.click(within(dialog).getByRole("radio", { name: /Kochi/ }));
    await user.click(within(dialog).getByRole("button", { name: "Switch" }));
    expect(
      await within(dialog).findByText("Your session was refreshed. Try again."),
    ).toBeInTheDocument();
    expect(api.callsTo("PUT /session/campus")).toHaveLength(1);
  });
});

describe("mobile (below 768px)", () => {
  it("moves Institute and Campus into the account menu", async () => {
    installColorScheme(false);
    const base = window.matchMedia.bind(window);
    window.matchMedia = (query: string) =>
      query === BELOW_TABLET
        ? { ...base(query), matches: true, media: query }
        : base(query);
    renderFrame(
      readySession({
        institutes: [INSTITUTES.coastal, INSTITUTES.harbour],
        campus_options: [CAMPUSES.kochi, CAMPUSES.vizag],
      }),
    );
    const user = userEvent.setup({ delay: null });
    const menu = await openAccountMenu(user);
    expect(
      within(menu).getByRole("menuitem", { name: /Institute/ }),
    ).toHaveTextContent("Coastal Maritime Training Institute");
    await user.click(within(menu).getByRole("menuitem", { name: /Campus/ }));
    expect(
      screen.getByRole("dialog", { name: "Switch campus" }),
    ).toBeInTheDocument();
  });
});

describe("other tabs", () => {
  it("shows the non-dismissible notice when another tab switched institute", async () => {
    const api = installFetch();
    api.on(
      "GET /session",
      ok(
        readySession({
          active_institute: INSTITUTES.harbour,
          institutes: [INSTITUTES.coastal, INSTITUTES.harbour],
        }),
      ),
    );
    renderFrame(
      readySession({ institutes: [INSTITUTES.coastal, INSTITUTES.harbour] }),
    );
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "visible",
    });
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    const notice = await screen.findByText(
      "You switched institute or campus in another tab.",
    );
    const user = userEvent.setup({ delay: null });
    await user.click(
      within(notice.closest("[role=status]")!).getByRole("button", {
        name: "Reload",
      }),
    );
    expect(navigation.reloadDocument).toHaveBeenCalled();
  });
});

describe("accessibility", () => {
  it.each(["light", "dark"] as const)(
    "passes axe in %s with all controls",
    async (theme) => {
      const { container } = renderFrame(
        readySession({
          institutes: [INSTITUTES.coastal, INSTITUTES.harbour],
          campus_options: [CAMPUSES.kochi, CAMPUSES.vizag],
          permissions: ["campus.read", "member.read", "role.read"],
        }),
        theme,
      );
      await expectNoA11yViolations(container);
    },
  );
});
