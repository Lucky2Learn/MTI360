import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { toastQueue } from "@/design-system/components";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { tenantListQuery } from "@/features/tenants/query";
import type { TenantDetailWire, TenantWire } from "@/lib/api/platform-tenants";
import type { ReadResult } from "@/lib/api/server-read";
import type { PlatformSessionWire } from "@/lib/api/types";
import { apiError, installFetch, jsonResponse, ok } from "@/test/fetch-mock";
import { PLATFORM_CSRF, platformSession } from "@/test/platform-fixtures";
import { renderScreen } from "@/test/render-screen";

import { PlatformFrame } from "../platform-frame";

import TenantDetailPage from "./[tenantId]/page";
import NewTenantPage from "./new/page";
import TenantsPage from "./page";

import type { ReactElement } from "react";

vi.setConfig({ testTimeout: 30_000 });

// Platform Tenants (PLAT-04 list, PLAT-05 detail, PLAT-06 create): the server
// gate (platform session → permission → read with the platform cookie), the
// list states, URL → API mapping, the owner-only detail, and the create form
// with client validation and API error mapping. The platform API authorizes
// every request again (backend tests: test_platform_tenants_api.py).

const KONKAN = "01a16e00-0000-7000-8000-00000000000a";
const COROMANDEL = "01a16e00-0000-7000-8000-00000000000b";

const state = vi.hoisted(() => ({
  session: null as PlatformSessionWire | null,
  reads: [] as { prefix: string; result: ReadResult<unknown> }[],
  readPaths: [] as string[],
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  search: "",
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/platform/tenants",
  useSearchParams: () => new URLSearchParams(state.search),
  useRouter: () => ({
    push: state.push,
    replace: state.replace,
    refresh: state.refresh,
  }),
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
  redirect: (url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`);
  },
}));
vi.mock("@/lib/session/platform-server", () => ({
  readPlatformSession: () => Promise.resolve(state.session),
  requirePlatformSession: (next: string) =>
    state.session
      ? Promise.resolve(state.session)
      : Promise.reject(
          new Error(
            `NEXT_REDIRECT /platform/session-ended?reason=ended&next=${encodeURIComponent(next)}`,
          ),
        ),
  SessionReadError: class extends Error {},
}));
// requireRecordId lives beside the tenant page gate; the tenant session is
// never read by these pages.
vi.mock("@/lib/session/server", () => ({
  requireReadyTenantSession: () => {
    throw new Error("a platform page must not read the tenant session");
  },
}));
vi.mock("@/lib/api/server-read", () => ({
  tenantApiRead: () => {
    throw new Error("a platform page must not read with the tenant cookie");
  },
  platformApiRead: (path: string) => {
    state.readPaths.push(path);
    const match = state.reads.find((read) => path.startsWith(read.prefix));
    return match
      ? Promise.resolve(match.result)
      : Promise.reject(new Error(`unexpected read ${path}`));
  },
}));
vi.mock("@/lib/env", () => ({
  getServerEnv: () => ({ appEnv: "production" }),
}));
vi.mock("@/lib/session/document", () => ({
  assignLocation: vi.fn(),
  reloadDocument: vi.fn(),
  currentPath: vi.fn(() => "/platform/tenants"),
}));

function tenant(overrides: Partial<TenantWire> = {}): TenantWire {
  return {
    id: KONKAN,
    name: "Konkan Maritime Training Institute",
    status: "ACTIVE",
    created_at: "2026-10-11T10:30:00Z",
    updated_at: "2026-10-12T08:15:00Z",
    version: 3,
    ...overrides,
  };
}

function detail(overrides: Partial<TenantDetailWire> = {}): TenantDetailWire {
  return {
    ...tenant(),
    owner: {
      display_name: "Capt. Anil Deshpande",
      email: "principal@konkan-maritime.example",
      status: "ACTIVE",
    },
    ...overrides,
  };
}

const okRead = <T,>(data: T, total = 1): ReadResult<T> => ({
  kind: "ok",
  data,
  page: { limit: 25, offset: 0, total },
});

function serve(prefix: string, result: ReadResult<unknown>) {
  state.reads.push({ prefix, result });
}

beforeEach(() => {
  state.session = platformSession();
  state.reads = [];
  state.readPaths = [];
  state.push.mockReset();
  state.replace.mockReset();
  state.refresh.mockReset();
  state.search = "";
});

afterEach(() => {
  vi.unstubAllGlobals();
  // Toasts are module state: one test's success must not satisfy another.
  act(() => toastQueue.clear());
});

async function show(
  page: Promise<ReactElement>,
  theme: "light" | "dark" = "light",
) {
  const element = await page;
  return renderScreen(
    <PlatformFrame session={state.session!} showUnreleased={false}>
      {element}
    </PlatformFrame>,
    { theme },
  );
}

const list = (params: Record<string, string> = {}) =>
  TenantsPage({ searchParams: Promise.resolve(params) });
const detailPage = (id: string = KONKAN) =>
  TenantDetailPage({ params: Promise.resolve({ tenantId: id }) });

const deniedHeading = () =>
  screen.getByRole("heading", { name: "You don't have access to this page" });

describe("PLAT-04 Tenant list: gate", () => {
  it("needs a full platform session first (session ended with next)", async () => {
    state.session = null;
    await expect(list()).rejects.toThrow(
      "NEXT_REDIRECT /platform/session-ended?reason=ended&next=%2Fplatform%2Ftenants",
    );
    expect(state.readPaths).toEqual([]);
  });

  it("without tenant.read: access denied at the same URL, no read, no permission or role named", async () => {
    state.session = platformSession({
      permissions: ["audit.read"],
      roles: ["SECURITY_AUDIT_ADMIN"],
    });
    const { container } = await show(list());
    expect(deniedHeading()).toBeInTheDocument();
    expect(screen.getByText(/ask a Super Admin/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/tenant\.read|SECURITY_AUDIT/);
    expect(state.readPaths).toEqual([]);
    await expectNoA11yViolations(container);
  });

  it("decides by permission, never by role name", async () => {
    state.session = platformSession({
      permissions: [],
      roles: ["SUPER_ADMIN"],
    });
    await show(list());
    expect(deniedHeading()).toBeInTheDocument();
    expect(state.readPaths).toEqual([]);
  });

  it("an API refusal of the read is access denied too", async () => {
    serve("/tenants", { kind: "denied" });
    await show(list());
    expect(deniedHeading()).toBeInTheDocument();
  });

  it("an ended session during the read goes to session ended", async () => {
    serve("/tenants", { kind: "unauthenticated" });
    await expect(list()).rejects.toThrow(
      "NEXT_REDIRECT /platform/session-ended?reason=ended&next=%2Fplatform%2Ftenants",
    );
  });
});

describe("PLAT-04 Tenant list: states", () => {
  it.each(["light", "dark"] as const)(
    "lists institutes with status and creation date, links to the detail, and passes axe (%s)",
    async (theme) => {
      serve(
        "/tenants",
        okRead(
          [
            tenant(),
            tenant({
              id: COROMANDEL,
              name: "Coromandel Nautical Academy",
              status: "TRIAL",
            }),
          ],
          2,
        ),
      );
      const { container } = await show(list(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "Tenants" }),
      ).toBeInTheDocument();
      const table = screen.getByRole("table", { name: "Tenants" });
      const konkan = within(table).getByRole("link", {
        name: "Konkan Maritime Training Institute",
      });
      expect(konkan).toHaveAttribute("href", `/platform/tenants/${KONKAN}`);
      expect(within(table).getByText("Trial")).toBeInTheDocument();
      expect(within(table).getByText("Active")).toBeInTheDocument();
      expect(within(table).getAllByText("11 Oct 2026").length).toBeGreaterThan(
        0,
      );
      expect(screen.getByText("2 tenants")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "New tenant" })).toHaveAttribute(
        "href",
        "/platform/tenants/new",
      );
      await expectNoA11yViolations(container);
    },
  );

  // No axe run here: DataTable renders its empty state as an h3 directly
  // under the page h1 (axe heading-order), a shared design-system behaviour
  // that Courses and Leads have too — reported, not changed in this module.
  it("empty: invites a Super Admin to provision the first institute", async () => {
    serve("/tenants", okRead([], 0));
    await show(list());
    expect(
      screen.getAllByRole("heading", { name: "No tenants yet" })[0],
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("link", { name: "New tenant" }).length,
    ).toBeGreaterThan(0);
  });

  it("without tenant.create: no create action anywhere", async () => {
    state.session = platformSession({ permissions: ["tenant.read"] });
    serve("/tenants", okRead([], 0));
    await show(list());
    expect(
      screen.getAllByText(
        "Institutes appear here once they are provisioned.",
      )[0],
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "New tenant" })).toBeNull();
  });

  it("filtered empty: offers to clear the filters", async () => {
    state.search = "q=harbour&status=SUSPENDED";
    serve("/tenants", okRead([], 0));
    await show(list({ q: "harbour", status: "SUSPENDED" }));
    expect(
      screen.getAllByRole("heading", {
        name: "No tenants match these filters",
      })[0],
    ).toBeInTheDocument();
    // The empty state's own button clears the search and the status (the
    // filter bar's "Clear filters" clears the status only).
    await userEvent.click(
      screen.getAllByRole("button", { name: "Clear filters" }).at(-1)!,
    );
    expect(state.replace).toHaveBeenCalledWith("/platform/tenants", {
      scroll: false,
    });
  });

  it("bounds the status filter so it sits beside the search and Clear filters", async () => {
    state.search = "status=TRIAL";
    serve("/tenants", okRead([], 0));
    await show(list({ status: "TRIAL" }));
    const group = screen.getByRole("group", { name: "Tenant filters" });
    // The Select root is full width; its wrapper sets the width from tablet.
    const wrapper = within(group)
      .getByText("Status")
      .closest(String.raw`div.tablet\:w-56`);
    expect(wrapper).toHaveClass("w-full");
    expect(wrapper?.parentElement).toBe(group);
    expect(
      within(group).getByRole("button", { name: "Clear filters" }),
    ).toBeInTheDocument();
  });

  it("error: fixed copy, the support reference and retry; never the server text", async () => {
    serve("/tenants", { kind: "error", reference: "req-7f3a" });
    const { container } = await show(list());
    expect(
      screen.getByRole("heading", { name: "Tenants couldn't be loaded" }),
    ).toBeInTheDocument();
    expect(container.textContent).toContain("req-7f3a");
    await userEvent.click(screen.getByRole("button", { name: /Try again/ }));
    expect(state.refresh).toHaveBeenCalled();
  });

  it("paginates when there are more tenants than one page", async () => {
    serve(
      "/tenants",
      okRead(
        Array.from({ length: 25 }, (_, index) =>
          tenant({
            id: `01a16e00-0000-7000-8000-${String(index).padStart(12, "0")}`,
            name: `Institute ${index + 1}`,
          }),
        ),
        60,
      ),
    );
    await show(list());
    const pages = screen.getAllByRole("navigation", {
      name: "Tenant pages",
    })[0]!;
    await userEvent.click(
      within(pages).getAllByRole("button", { name: /Next/ })[0]!,
    );
    expect(state.replace).toHaveBeenCalledWith("/platform/tenants?offset=25", {
      scroll: false,
    });
  });

  it("a page past the end (stale link) offers the first page, not 'No tenants yet'", async () => {
    state.search = "offset=500";
    serve("/tenants", {
      kind: "ok",
      data: [],
      page: { limit: 25, offset: 500, total: 3 },
    });
    await show(list({ offset: "500" }));
    expect(
      screen.queryByRole("heading", { name: "No tenants yet" }),
    ).toBeNull();
    expect(
      screen.getAllByRole("heading", { name: "No tenants on this page" })[0],
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getAllByRole("button", { name: "Go to the first page" })[0]!,
    );
    expect(state.replace).toHaveBeenCalledWith("/platform/tenants", {
      scroll: false,
    });
  });

  it.each([
    ["", "Created", "descending"],
    ["sort=name", "Institute", "ascending"],
    ["sort=-name", "Institute", "descending"],
    // Dropped by the URL → API mapping, so the default order is shown.
    ["sort=status", "Created", "descending"],
    ["sort=owner", "Created", "descending"],
  ])(
    "the sorted column shows the order the API was asked for (%s)",
    async (search, column, direction) => {
      state.search = search;
      serve("/tenants", okRead([tenant()], 1));
      await show(list(Object.fromEntries(new URLSearchParams(search))));
      const table = screen.getByRole("table", { name: "Tenants" });
      expect(
        within(table).getByRole("columnheader", { name: new RegExp(column) }),
      ).toHaveAttribute("aria-sort", direction);
    },
  );
});

describe("PLAT-04 Tenant list: URL → API", () => {
  it("reads with the default sort and page size", async () => {
    serve("/tenants", okRead([], 0));
    await show(list());
    expect(state.readPaths).toEqual([
      "/tenants?sort=-created_at&limit=25&offset=0",
    ]);
  });

  it("forwards known keys and drops unknown or invalid values", () => {
    expect(
      tenantListQuery({
        q: "  Konkan ",
        status: "SUSPENDED",
        sort: "name",
        offset: "50",
        tenant_id: "forged",
      }),
    ).toBe("q=Konkan&status=SUSPENDED&sort=name&limit=25&offset=50");
    expect(
      tenantListQuery({ status: "DELETED", sort: "owner", offset: "-5" }),
    ).toBe("sort=-created_at&limit=25&offset=0");
  });

  it("aligns a hand-edited offset to the start of its page", () => {
    expect(tenantListQuery({ offset: "10" })).toBe(
      "sort=-created_at&limit=25&offset=0",
    );
    expect(tenantListQuery({ offset: "60" })).toBe(
      "sort=-created_at&limit=25&offset=50",
    );
  });
});

describe("PLAT-05 Tenant detail", () => {
  it.each(["light", "dark"] as const)(
    "shows the status, dates and the administrator only, and passes axe (%s)",
    async (theme) => {
      serve(`/tenants/${KONKAN}`, okRead(detail()));
      const { container } = await show(detailPage(), theme);
      expect(
        screen.getByRole("heading", {
          level: 1,
          name: "Konkan Maritime Training Institute",
        }),
      ).toBeInTheDocument();
      expect(
        screen.getByText("principal@konkan-maritime.example"),
      ).toBeInTheDocument();
      expect(screen.getByText("Joined")).toBeInTheDocument();
      const breadcrumb = screen.getByRole("navigation", { name: "Breadcrumb" });
      expect(
        within(breadcrumb).getByRole("link", { name: "Tenants" }),
      ).toHaveAttribute("href", "/platform/tenants");
      expect(state.readPaths).toEqual([`/tenants/${KONKAN}`]);
      await expectNoA11yViolations(container);
    },
  );

  it("an administrator who has not joined is shown as invited", async () => {
    serve(
      `/tenants/${COROMANDEL}`,
      okRead(
        detail({
          id: COROMANDEL,
          name: "Coromandel Nautical Academy",
          status: "TRIAL",
          owner: {
            display_name: "Capt. R. Venkatesan",
            email: "director@coromandel-nautical.example",
            status: "INVITED",
          },
        }),
      ),
    );
    await show(detailPage(COROMANDEL));
    expect(screen.getByText("Invitation sent")).toBeInTheDocument();
    expect(screen.getAllByText("Trial").length).toBeGreaterThan(0);
  });

  it("a malformed or unknown ID is not found; no session or permission comes first", async () => {
    await expect(detailPage("not-a-uuid")).rejects.toThrow("NEXT_NOT_FOUND");
    serve(`/tenants/${KONKAN}`, { kind: "not-found" });
    await expect(detailPage()).rejects.toThrow("NEXT_NOT_FOUND");
    state.session = platformSession({ permissions: ["audit.read"] });
    await show(detailPage());
    expect(deniedHeading()).toBeInTheDocument();
    state.session = null;
    await expect(detailPage()).rejects.toThrow("NEXT_REDIRECT");
  });

  it("a failed read shows the error state with the reference", async () => {
    serve(`/tenants/${KONKAN}`, { kind: "error", reference: "req-91" });
    const { container } = await show(detailPage());
    expect(
      screen.getByRole("heading", { name: "This tenant couldn't be loaded" }),
    ).toBeInTheDocument();
    expect(container.textContent).toContain("req-91");
  });
});

describe("PLAT-05 Tenant actions: suspend and reactivate", () => {
  const SUSPEND = `POST /platform/tenants/${KONKAN}/suspend`;
  const REACTIVATE = `POST /platform/tenants/${KONKAN}/reactivate`;
  const button = (name: string) => screen.queryByRole("button", { name });

  async function suspendWith(reason: string) {
    await userEvent.click(button("Suspend tenant")!);
    const dialog = await screen.findByRole("dialog", {
      name: /Suspend Konkan Maritime Training Institute/,
    });
    if (reason)
      await userEvent.type(
        within(dialog).getByRole("textbox", { name: /Reason/ }),
        reason,
      );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Suspend tenant" }),
    );
    return dialog;
  }

  it.each([
    ["TRIAL", ["tenant.suspend"], "Suspend tenant"],
    ["ACTIVE", ["tenant.suspend"], "Suspend tenant"],
    ["PAST_DUE", ["tenant.suspend"], "Suspend tenant"],
    ["SUSPENDED", ["tenant.reactivate"], "Reactivate tenant"],
  ] as const)(
    "%s with %s offers %s only",
    async (status, permissions, offered) => {
      state.session = platformSession({
        permissions: ["tenant.read", ...permissions],
      });
      serve(`/tenants/${KONKAN}`, okRead(detail({ status })));
      await show(detailPage());
      expect(button(offered)).toBeInTheDocument();
      const other =
        offered === "Suspend tenant" ? "Reactivate tenant" : "Suspend tenant";
      expect(button(other)).toBeNull();
    },
  );

  it("without the permission, or in a status the API won't change: no button", async () => {
    state.session = platformSession({ permissions: ["tenant.read"] });
    serve(`/tenants/${KONKAN}`, okRead(detail()));
    await show(detailPage());
    expect(button("Suspend tenant")).toBeNull();
    state.session = platformSession();
    state.reads = [];
    serve(`/tenants/${KONKAN}`, okRead(detail({ status: "CANCELLED" })));
    await show(detailPage());
    expect(button("Suspend tenant")).toBeNull();
    expect(button("Reactivate tenant")).toBeNull();
  });

  it.each(["light", "dark"] as const)(
    "the confirmation needs a reason before anything is sent, and passes axe (%s)",
    async (theme) => {
      const api = installFetch();
      serve(`/tenants/${KONKAN}`, okRead(detail()));
      await show(detailPage(), theme);
      const dialog = await suspendWith("");
      expect(
        await within(dialog).findByText("Enter a reason."),
      ).toBeInTheDocument();
      expect(within(dialog).getByText(/signed out at once/)).toBeVisible();
      expect(api.calls).toHaveLength(0);
      await expectNoA11yViolations(dialog);
    },
  );

  it("suspend: step-up → exactly one resend with the reason and version → success, then a re-read", async () => {
    const api = installFetch();
    api.on(
      SUSPEND,
      apiError(403, "STEP_UP_REQUIRED"),
      ok(detail({ status: "SUSPENDED", version: 4 })),
    );
    api.on("POST /platform/session/step-up", ok(platformSession()));
    serve(`/tenants/${KONKAN}`, okRead(detail()));
    await show(detailPage());
    await suspendWith("Compliance hold: DG Shipping audit");
    await screen.findByRole("dialog", { name: "Confirm it's you" });
    expect(state.refresh).not.toHaveBeenCalled();
    await userEvent.type(
      screen.getByLabelText(/Authentication code/),
      "654321",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Verify and continue" }),
    );
    expect(
      await screen.findByText(
        "Konkan Maritime Training Institute is suspended",
      ),
    ).toBeInTheDocument();
    const calls = api.callsTo(SUSPEND);
    expect(calls).toHaveLength(2);
    expect(calls[1]!.body).toEqual({
      reason: "Compliance hold: DG Shipping audit",
      version: 3,
    });
    expect(calls[1]!.headers["x-csrf-token"]).toBe(PLATFORM_CSRF);
    expect(state.refresh).toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("cancelling step-up changes nothing and says so", async () => {
    const api = installFetch();
    api.on(SUSPEND, apiError(403, "STEP_UP_REQUIRED"));
    serve(`/tenants/${KONKAN}`, okRead(detail()));
    await show(detailPage());
    const dialog = await suspendWith("Unpaid invoices");
    await screen.findByRole("dialog", { name: "Confirm it's you" });
    await userEvent.click(
      within(
        screen.getByRole("dialog", { name: "Confirm it's you" }),
      ).getByRole("button", { name: "Cancel" }),
    );
    expect(
      await within(dialog).findByText("The institute wasn't suspended"),
    ).toBeInTheDocument();
    expect(api.callsTo(SUSPEND)).toHaveLength(1);
    expect(state.refresh).not.toHaveBeenCalled();
    expect(screen.queryByText(/is suspended/)).toBeNull();
  });

  // D6-5: the API alone decides freshness (10 minutes after the last MFA
  // verification, sign-in included); the browser never prompts on its own.
  it("a fresh verification: one request, no authenticator prompt", async () => {
    const api = installFetch();
    api.on(SUSPEND, ok(detail({ status: "SUSPENDED", version: 4 })));
    serve(`/tenants/${KONKAN}`, okRead(detail()));
    await show(detailPage());
    await suspendWith("Unpaid invoices");
    expect(
      await screen.findByText(
        "Konkan Maritime Training Institute is suspended",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("dialog", { name: "Confirm it's you" }),
    ).toBeNull();
    expect(api.callsTo(SUSPEND)).toHaveLength(1);
    expect(api.callsTo("POST /platform/session/step-up")).toHaveLength(0);
  });

  it("reactivate: a second STEP_UP_REQUIRED after a code stops with an error, no success", async () => {
    const api = installFetch();
    api.on(
      REACTIVATE,
      apiError(403, "STEP_UP_REQUIRED"),
      apiError(403, "STEP_UP_REQUIRED"),
    );
    api.on("POST /platform/session/step-up", ok(platformSession()));
    serve(`/tenants/${KONKAN}`, okRead(detail({ status: "SUSPENDED" })));
    await show(detailPage());
    await userEvent.click(button("Reactivate tenant")!);
    const dialog = await screen.findByRole("dialog", {
      name: /Reactivate Konkan/,
    });
    await userEvent.type(
      within(dialog).getByRole("textbox", { name: /Reason/ }),
      "Audit closed",
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Reactivate tenant" }),
    );
    await screen.findByRole("dialog", { name: "Confirm it's you" });
    await userEvent.type(
      screen.getByLabelText(/Authentication code/),
      "654321",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Verify and continue" }),
    );
    expect(
      await within(dialog).findByText(
        "We couldn't confirm it's you. Try again.",
      ),
    ).toBeInTheDocument();
    expect(api.callsTo(REACTIVATE)).toHaveLength(2);
    expect(screen.queryByText(/is active again/)).toBeNull();
    expect(state.refresh).not.toHaveBeenCalled();
  });

  it("a stale version or a refused transition (409) shows no success and re-reads", async () => {
    const api = installFetch();
    api.on(SUSPEND, apiError(409, "CONFLICT"));
    serve(`/tenants/${KONKAN}`, okRead(detail()));
    const { container } = await show(detailPage());
    const dialog = await suspendWith("Unpaid invoices");
    expect(
      await within(dialog).findByText("The institute wasn't suspended"),
    ).toBeInTheDocument();
    expect(state.refresh).toHaveBeenCalled();
    expect(screen.queryByText(/is suspended/)).toBeNull();
    expect(container.textContent).not.toContain("SERVER-");
  });

  it("a reason the API refuses (422) is shown on the field; a denial uses fixed copy", async () => {
    const api = installFetch();
    api.on(
      SUSPEND,
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "reason", code: "reason_required" }],
      }),
      apiError(403, "PERMISSION_DENIED"),
    );
    api.on("GET /platform/session", ok(platformSession()));
    serve(`/tenants/${KONKAN}`, okRead(detail()));
    await show(detailPage());
    const dialog = await suspendWith("x");
    expect(
      await within(dialog).findByText(
        "Enter a reason of up to 500 characters.",
      ),
    ).toBeInTheDocument();
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Suspend tenant" }),
    );
    expect(
      await within(dialog).findByText("You can't do this"),
    ).toBeInTheDocument();
    expect(state.refresh).not.toHaveBeenCalled();
  });

  it("reactivate sends the reason and version and confirms only after the API answers", async () => {
    const api = installFetch();
    api.on(REACTIVATE, ok(detail({ status: "ACTIVE", version: 5 })));
    serve(`/tenants/${KONKAN}`, okRead(detail({ status: "SUSPENDED" })));
    await show(detailPage());
    await userEvent.click(button("Reactivate tenant")!);
    const dialog = await screen.findByRole("dialog", {
      name: /Reactivate Konkan/,
    });
    expect(dialog).toHaveTextContent(/sessions ended by the suspension/);
    await userEvent.type(
      within(dialog).getByRole("textbox", { name: /Reason/ }),
      "Audit closed",
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Reactivate tenant" }),
    );
    expect(
      await screen.findByText(
        "Konkan Maritime Training Institute is active again",
      ),
    ).toBeInTheDocument();
    expect(api.callsTo(REACTIVATE)[0]!.body).toEqual({
      reason: "Audit closed",
      version: 3,
    });
  });
});

describe("PLAT-05 Tenant actions: resend the owner invitation", () => {
  const RESEND = `POST /platform/tenants/${KONKAN}/owner-invitation/resend`;
  const invited = () =>
    detail({
      status: "TRIAL",
      owner: {
        display_name: "Capt. Anil Deshpande",
        email: "principal@konkan-maritime.example",
        status: "INVITED",
      },
    });

  async function resend() {
    await userEvent.click(
      screen.getByRole("button", { name: "Resend invitation" }),
    );
    const confirm = await screen.findByRole("alertdialog", {
      name: "Send a new invitation?",
    });
    expect(confirm).toHaveTextContent(/previous invitation link stops working/);
    await userEvent.click(
      within(confirm).getByRole("button", { name: "Send new invitation" }),
    );
  }

  it("offered only while the administrator has not joined, with tenant.create", async () => {
    serve(`/tenants/${KONKAN}`, okRead(detail()));
    await show(detailPage());
    expect(
      screen.queryByRole("button", { name: "Resend invitation" }),
    ).toBeNull();
    state.reads = [];
    state.session = platformSession({ permissions: ["tenant.read"] });
    serve(`/tenants/${KONKAN}`, okRead(invited()));
    await show(detailPage());
    expect(
      screen.queryByRole("button", { name: "Resend invitation" }),
    ).toBeNull();
  });

  it("202: says the email is being sent (never that it arrived)", async () => {
    const api = installFetch();
    api.on(RESEND, jsonResponse(202, null));
    serve(`/tenants/${KONKAN}`, okRead(invited()));
    await show(detailPage());
    await resend();
    expect(
      await screen.findByText("A new invitation was issued"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/being emailed to principal@konkan-maritime.example/),
    ).toBeInTheDocument();
    const [call] = api.callsTo(RESEND);
    expect(call!.headers["x-csrf-token"]).toBe(PLATFORM_CSRF);
  });

  it("409 (already joined or disabled): no success, a re-read", async () => {
    const api = installFetch();
    api.on(RESEND, apiError(409, "CONFLICT"));
    serve(`/tenants/${KONKAN}`, okRead(invited()));
    await show(detailPage());
    await resend();
    expect(
      await screen.findByText("The invitation wasn't resent"),
    ).toBeInTheDocument();
    expect(screen.queryByText("A new invitation was issued")).toBeNull();
    expect(state.refresh).toHaveBeenCalled();
  });

  it("a failed request shows an error, never success", async () => {
    const api = installFetch();
    api.on(RESEND, apiError(500, "INTERNAL_ERROR"));
    serve(`/tenants/${KONKAN}`, okRead(invited()));
    await show(detailPage());
    await resend();
    expect(
      await screen.findByText("Something went wrong. Try again in a moment."),
    ).toBeInTheDocument();
    expect(screen.queryByText("A new invitation was issued")).toBeNull();
  });
});

describe("PLAT-06 Create tenant", () => {
  const field = (name: string) => screen.getByRole("textbox", { name });

  async function fill(values: Partial<Record<string, string>> = {}) {
    const all = {
      "Institute name": "Malabar Marine Academy",
      "Primary campus name": "Kochi Campus",
      "Campus code": "koc",
      "Full name": "Capt. Thomas Mathew",
      Email: "principal@malabar-marine.example",
      ...values,
    };
    for (const [label, value] of Object.entries(all)) {
      if (value) await userEvent.type(field(label), value);
    }
  }

  const submit = () =>
    userEvent.click(screen.getByRole("button", { name: "Create tenant" }));

  it("needs tenant.create (access denied at the same URL)", async () => {
    state.session = platformSession({ permissions: ["tenant.read"] });
    await show(NewTenantPage());
    expect(deniedHeading()).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Create tenant" })).toBeNull();
  });

  it.each(["light", "dark"] as const)(
    "validates locally before sending anything, and passes axe (%s)",
    async (theme) => {
      const api = installFetch();
      const { container } = await show(NewTenantPage(), theme);
      await fill({ "Campus code": "-bad code", Email: "not-an-email" });
      await userEvent.clear(field("Institute name"));
      await submit();
      expect(
        await screen.findByText("Enter the institute's name."),
      ).toBeInTheDocument();
      expect(screen.getByText(/Use up to 32 letters/)).toBeInTheDocument();
      expect(
        screen.getByText(/Enter an email address like/),
      ).toBeInTheDocument();
      expect(api.calls).toHaveLength(0);
      await expectNoA11yViolations(container);
    },
  );

  it("provisions with the CSRF token and the exact body, then opens the new tenant", async () => {
    const api = installFetch();
    api.on(
      "POST /platform/tenants",
      jsonResponse(201, {
        data: {
          tenant: detail({ id: COROMANDEL, name: "Malabar Marine Academy" }),
          campus: { id: "c1", name: "Kochi Campus", code: "KOC" },
          owner_account: "new",
        },
      }),
    );
    await show(NewTenantPage());
    await fill();
    await submit();
    await waitFor(() =>
      expect(state.push).toHaveBeenCalledWith(
        `/platform/tenants/${COROMANDEL}`,
      ),
    );
    const [call] = api.callsTo("POST /platform/tenants");
    expect(call?.headers["x-csrf-token"]).toBe(PLATFORM_CSRF);
    expect(call?.body).toEqual({
      name: "Malabar Marine Academy",
      campus: { name: "Kochi Campus", code: "KOC" },
      owner: {
        display_name: "Capt. Thomas Mathew",
        email: "principal@malabar-marine.example",
      },
    });
    expect(state.refresh).toHaveBeenCalled();
  });

  it("maps API field errors to the form's own copy", async () => {
    const api = installFetch();
    api.on(
      "POST /platform/tenants",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "campus.code", code: "invalid" }],
      }),
    );
    const { container } = await show(NewTenantPage());
    await fill();
    await submit();
    expect(await screen.findByText(/Use up to 32 letters/)).toBeInTheDocument();
    expect(container.textContent).not.toContain("SERVER-");
    expect(state.push).not.toHaveBeenCalled();
  });

  it("a conflict (disabled account) is explained without the server message", async () => {
    const api = installFetch();
    api.on("POST /platform/tenants", apiError(409, "CONFLICT"));
    const { container } = await show(NewTenantPage());
    await fill();
    await submit();
    expect(
      await screen.findByText("The tenant wasn't created"),
    ).toBeInTheDocument();
    expect(container.textContent).not.toContain("SERVER-");
    expect(state.push).not.toHaveBeenCalled();
  });
});
