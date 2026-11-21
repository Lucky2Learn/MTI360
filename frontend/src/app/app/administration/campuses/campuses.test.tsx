import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockInstance,
} from "vitest";

import { toast } from "@/design-system/components";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import { codeError, nameError } from "@/features/campuses/labels";
import { formatDate } from "@/features/shared/format";
import type { ReadResult } from "@/lib/api/server-read";
import type { SessionWire } from "@/lib/api/types";
import { ok } from "@/test/admissions-fixtures";
import { apiError, installFetch, jsonResponse } from "@/test/fetch-mock";
import { CAMPUSES, readySession } from "@/test/session-fixtures";
import { campus, CAMPUS_LIST } from "@/test/tenant-admin-fixtures";

import TenantLoading from "../../loading";
import { TenantFrame } from "../../tenant-frame";

import CampusDetailPage from "./[campusId]/page";
import CampusesPage from "./page";

import type { ReactElement } from "react";

vi.setConfig({ testTimeout: 30_000 });

// ADMIN-03 Campuses and ADMIN-04 Campus detail (02-C over the T01-08 API):
// the server gate, list and detail states, Add campus (validation, an
// uppercase code, 409 on a taken code), Rename (version, 409, 404, 403,
// 422) and the immutable code. All API calls are scripted: no campus is
// created and no database is touched.

const state = vi.hoisted(() => ({
  session: null as SessionWire | null,
  reads: [] as [string, ReadResult<unknown>][],
  refresh: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/app/administration/campuses",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: state.refresh,
  }),
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
  redirect: (url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`);
  },
}));
vi.mock("@/lib/session/server", () => ({
  readTenantSession: () => Promise.resolve(state.session),
  requireReadyTenantSession: (next: string) =>
    state.session
      ? Promise.resolve(state.session)
      : Promise.reject(new Error(`NEXT_REDIRECT /session-ended?next=${next}`)),
}));
vi.mock("@/lib/api/server-read", () => ({
  tenantApiRead: (path: string) => {
    const found = state.reads.find(([pattern]) => path === pattern);
    return found
      ? Promise.resolve(found[1])
      : Promise.reject(new Error(`unexpected read ${path}`));
  },
}));

const toasts = {} as Record<
  "success" | "warning" | "error" | "info",
  MockInstance<(typeof toast)["success"]>
>;

const ADMIN = ["campus.read", "campus.create", "campus.update"];

const admin = (overrides: Partial<SessionWire> = {}) =>
  readySession({
    permissions: ADMIN,
    all_campuses_allowed: true,
    campus_options: [CAMPUSES.kochi, CAMPUSES.vizag],
    ...overrides,
  });

beforeEach(() => {
  state.session = admin();
  state.reads = [];
  state.refresh.mockReset();
  for (const tone of ["success", "warning", "error", "info"] as const) {
    toasts[tone] = vi.spyOn(toast, tone).mockReturnValue("toast");
  }
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function show(
  page: Promise<ReactElement> | ReactElement,
  theme: "light" | "dark" = "light",
) {
  const element = await page;
  document.documentElement.dataset.theme = theme;
  return render(
    <ThemeProvider>
      <TenantFrame session={state.session!} showUnreleased={false}>
        {element}
      </TenantFrame>
    </ThemeProvider>,
  );
}

const KOCHI = campus();
const list = () => CampusesPage();
const detail = (id: string = KOCHI.id) =>
  CampusDetailPage({ params: Promise.resolve({ campusId: id }) });
const detailPath = `/app/administration/campuses/${KOCHI.id}`;

const accessDenied = () =>
  screen.getByRole("heading", { name: "You don't have access to this page" });

// --- ADMIN-03 -------------------------------------------------------------------

describe("ADMIN-03 Campuses", () => {
  it("needs a session first, then campus.read (AUTHZ-01 at the same URL)", async () => {
    state.session = null;
    await expect(list()).rejects.toThrow(
      "NEXT_REDIRECT /session-ended?next=/app/administration/campuses",
    );
    state.session = readySession({ permissions: ["member.read"] });
    await show(list());
    expect(accessDenied()).toBeInTheDocument();
  });

  it.each(["light", "dark"] as const)(
    "lists campuses with name, code and links, and passes axe (%s)",
    async (theme) => {
      state.reads = [["/campuses", ok(CAMPUS_LIST, 2)]];
      const { container } = await show(list(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "Campuses" }),
      ).toBeInTheDocument();
      const table = screen.getByRole("table", { name: "Campuses" });
      const vizag = within(table).getByRole("row", {
        name: /Visakhapatnam Campus/,
      });
      expect(within(vizag).getByText("VTZ")).toBeInTheDocument();
      expect(
        within(table).getByRole("link", { name: "Kochi Campus" }),
      ).toHaveAttribute("href", detailPath);
      expect(
        screen.getByRole("button", { name: "Add campus" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /archive|delete/i }),
      ).toBeNull();
      await expectNoA11yViolations(container);
    },
  );

  it("turns rows into cards below tablet and hides the date columns on mobile", async () => {
    state.reads = [["/campuses", ok(CAMPUS_LIST, 2)]];
    await show(list());
    const cards = screen.getByRole("list", { name: "Campuses" });
    expect(cards.parentElement).toHaveClass("tablet:hidden");
    expect(within(cards).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("columnheader", { name: "Added" })).toHaveClass(
      "hidden",
      "tablet:table-cell",
    );
    expect(
      screen.getByRole("columnheader", { name: "Last changed" }),
    ).toHaveClass("hidden", "desktop:table-cell");
  });

  it("offers no Add campus without campus.create, including in the empty state", async () => {
    state.session = admin({ permissions: ["campus.read"] });
    state.reads = [["/campuses", ok([], 0)]];
    await show(list());
    expect(screen.getAllByText("No campuses to show").length).toBeGreaterThan(
      0,
    );
    expect(screen.queryByRole("button", { name: "Add campus" })).toBeNull();
  });

  it("explains an empty list and offers Add campus with campus.create", async () => {
    state.reads = [["/campuses", ok([], 0)]];
    await show(list());
    expect(screen.getAllByText("No campuses yet").length).toBeGreaterThan(0);
    expect(
      screen.getAllByRole("button", { name: "Add campus" }).length,
    ).toBeGreaterThan(1);
  });

  it("shows the error state with the reference, and AUTHZ-01 when the API refuses", async () => {
    state.reads = [["/campuses", { kind: "error", reference: "req-3301" }]];
    const { unmount } = await show(list());
    expect(
      screen.getByRole("heading", { name: "Campuses couldn't be loaded" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/req-3301/)).toBeInTheDocument();
    unmount();
    state.reads = [["/campuses", { kind: "denied" }]];
    await show(list());
    expect(accessDenied()).toBeInTheDocument();
  });

  it("shows the shell skeleton while the page loads", async () => {
    await show(<TenantLoading />);
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-busy", "true");
    expect(region).toHaveTextContent("Loading page");
  });
});

// --- Add campus -----------------------------------------------------------------

describe("Add campus", () => {
  async function openAdd() {
    state.reads = [["/campuses", ok(CAMPUS_LIST, 2)]];
    const user = userEvent.setup();
    const view = await show(list());
    await user.click(screen.getByRole("button", { name: "Add campus" }));
    const dialog = await screen.findByRole("dialog", { name: "Add campus" });
    return { user, dialog, view };
  }

  it("validates the name and code before sending", async () => {
    const api = installFetch();
    const { user, dialog } = await openAdd();
    await user.type(
      within(dialog).getByRole("textbox", { name: /Campus code/ }),
      "-goa x",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Add campus" }),
    );
    expect(
      within(dialog).getByText("Enter a campus name of up to 200 characters."),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        "Use up to 32 letters, digits or hyphens, starting with a letter or digit.",
      ),
    ).toBeInTheDocument();
    expect(api.callsTo("POST /campuses")).toHaveLength(0);
  });

  it("an empty form shows both errors, focuses Campus name and sends nothing", async () => {
    const api = installFetch();
    const { user, dialog } = await openAdd();
    await user.click(
      within(dialog).getByRole("button", { name: "Add campus" }),
    );
    expect(
      within(dialog).getByText("Enter a campus name of up to 200 characters."),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        "Use up to 32 letters, digits or hyphens, starting with a letter or digit.",
      ),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        within(dialog).getByRole("textbox", { name: /Campus name/ }),
      ).toHaveFocus(),
    );
    expect(api.calls).toHaveLength(0);
  });

  it("a code starting with a hyphen and an empty name are refused before sending", async () => {
    const api = installFetch();
    const { user, dialog } = await openAdd();
    const code = within(dialog).getByRole("textbox", { name: /Campus code/ });
    await user.type(code, "-KOC");
    await user.click(
      within(dialog).getByRole("button", { name: "Add campus" }),
    );
    expect(code).toHaveAttribute("aria-invalid", "true");
    expect(
      within(dialog).getByText(
        "Use up to 32 letters, digits or hyphens, starting with a letter or digit.",
      ),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText("Enter a campus name of up to 200 characters."),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        within(dialog).getByRole("textbox", { name: /Campus name/ }),
      ).toHaveFocus(),
    );
    expect(api.calls).toHaveLength(0);
  });

  it("uppercases the code, sends name and code only, and refreshes the list", async () => {
    const api = installFetch();
    api.on(
      "POST /campuses",
      jsonResponse(201, {
        data: campus({
          id: "c5f3e4d6-7b8a-4192-8cbd-2e3f4a5b6c33",
          name: "Goa Campus",
          code: "GOA-01",
        }),
        meta: {},
      }),
    );
    const { user, dialog, view } = await openAdd();
    await user.type(
      within(dialog).getByRole("textbox", { name: /Campus name/ }),
      "  Goa   Campus ",
    );
    const code = within(dialog).getByRole("textbox", { name: /Campus code/ });
    await user.type(code, "goa-01");
    expect(code).toHaveValue("GOA-01");
    expect(within(dialog).getByText(/It can't be changed later/)).toBeVisible();
    await expectNoA11yViolations(view.container);
    await user.click(
      within(dialog).getByRole("button", { name: "Add campus" }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(api.callsTo("POST /campuses")[0]!.body).toEqual({
      name: "Goa   Campus",
      code: "GOA-01",
    });
    expect(toasts.success).toHaveBeenCalledWith("Goa Campus (GOA-01) added.");
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Add campus" })).toBeNull(),
    );
  });

  it("a 409 marks the code as taken and keeps the dialog open", async () => {
    const api = installFetch();
    api.on("POST /campuses", apiError(409, "CONFLICT"));
    const { user, dialog } = await openAdd();
    await user.type(
      within(dialog).getByRole("textbox", { name: /Campus name/ }),
      "Kochi Annexe",
    );
    await user.type(
      within(dialog).getByRole("textbox", { name: /Campus code/ }),
      "koc",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Add campus" }),
    );
    expect(
      await within(dialog).findByText("Another campus already uses this code."),
    ).toBeInTheDocument();
    expect(toasts.success).not.toHaveBeenCalled();
    expect(state.refresh).not.toHaveBeenCalled();
    expect(screen.queryByText(/SERVER-MESSAGE/)).toBeNull();
  });

  it.each([
    [
      "a 422 maps field errors",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "code", code: "invalid" }],
      }),
      "Use up to 32 letters, digits or hyphens, starting with a letter or digit.",
    ],
    [
      "a 403 explains the refusal",
      apiError(403, "PERMISSION_DENIED"),
      "You can't add campuses",
    ],
  ])("%s without a success message", async (_label, response, text) => {
    const api = installFetch();
    api.on("POST /campuses", response);
    const { user, dialog } = await openAdd();
    await user.type(
      within(dialog).getByRole("textbox", { name: /Campus name/ }),
      "Goa Campus",
    );
    await user.type(
      within(dialog).getByRole("textbox", { name: /Campus code/ }),
      "GOA",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Add campus" }),
    );
    expect(await within(dialog).findByText(text)).toBeInTheDocument();
    expect(toasts.success).not.toHaveBeenCalled();
    expect(screen.queryByText(/SERVER-/)).toBeNull();
  });
});

// --- ADMIN-04 -------------------------------------------------------------------

describe("ADMIN-04 Campus detail", () => {
  it("needs campus.read; another institute's or an out-of-scope campus, or a malformed ID, is not found", async () => {
    state.session = admin({ permissions: ["member.read"] });
    await show(detail());
    expect(accessDenied()).toBeInTheDocument();

    state.session = admin();
    state.reads = [[`/campuses/${KOCHI.id}`, { kind: "not-found" }]];
    await expect(detail()).rejects.toThrow("NEXT_NOT_FOUND");
    await expect(detail("KOC")).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("sends an ended session to sign in, and shows the error state or AUTHZ-01", async () => {
    state.reads = [[`/campuses/${KOCHI.id}`, { kind: "unauthenticated" }]];
    await expect(detail()).rejects.toThrow(
      `NEXT_REDIRECT /session-ended?reason=ended&next=${encodeURIComponent(detailPath)}`,
    );
    state.reads = [
      [`/campuses/${KOCHI.id}`, { kind: "error", reference: "req-3302" }],
    ];
    const { unmount } = await show(detail());
    expect(
      screen.getByRole("heading", { name: "This campus couldn't be loaded" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/req-3302/)).toBeInTheDocument();
    unmount();
    state.reads = [[`/campuses/${KOCHI.id}`, { kind: "denied" }]];
    await show(detail());
    expect(accessDenied()).toBeInTheDocument();
  });

  it.each(["light", "dark"] as const)(
    "shows the campus with its permanent code and passes axe (%s)",
    async (theme) => {
      state.reads = [[`/campuses/${KOCHI.id}`, ok(KOCHI)]];
      const { container } = await show(detail(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "Kochi Campus" }),
      ).toBeInTheDocument();
      const details = screen.getByRole("region", { name: "Details" });
      expect(within(details).getByText("KOC")).toBeInTheDocument();
      expect(
        within(details).getByText(/It can't be changed\./),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Rename" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /archive|delete/i }),
      ).toBeNull();
      await expectNoA11yViolations(container);
    },
  );

  it("shows the breadcrumb back to Campuses and the added and last-changed dates", async () => {
    const changed = campus({
      updated_at: "2026-10-12T15:30:00+05:30",
      version: 3,
    });
    state.reads = [[`/campuses/${KOCHI.id}`, ok(changed)]];
    await show(detail());
    const trail = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(trail).getByText("Administration")).toBeInTheDocument();
    expect(
      within(trail).getByRole("link", { name: "Campuses" }),
    ).toHaveAttribute("href", "/app/administration/campuses");
    expect(within(trail).getByText("Campus")).toHaveAttribute(
      "aria-current",
      "page",
    );
    const details = screen.getByRole("region", { name: "Details" });
    const added = formatDate(changed.created_at);
    const lastChanged = formatDate(changed.updated_at);
    expect(added).toMatch(/2026/);
    expect(lastChanged).not.toBe(added);
    expect(
      within(details).getByText("Added").nextElementSibling,
    ).toHaveTextContent(added);
    expect(
      within(details).getByText("Last changed").nextElementSibling,
    ).toHaveTextContent(lastChanged);
  });

  it("offers no rename without campus.update", async () => {
    state.session = admin({ permissions: ["campus.read"] });
    state.reads = [[`/campuses/${KOCHI.id}`, ok(KOCHI)]];
    await show(detail());
    expect(screen.queryByRole("button", { name: "Rename" })).toBeNull();
  });
});

// --- Rename campus --------------------------------------------------------------

describe("Rename campus", () => {
  async function openRename() {
    state.reads = [[`/campuses/${KOCHI.id}`, ok(KOCHI)]];
    const user = userEvent.setup();
    const view = await show(detail());
    await user.click(screen.getByRole("button", { name: "Rename" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Rename campus",
    });
    return { user, dialog, view };
  }
  const name = (dialog: HTMLElement) =>
    within(dialog).getByRole("textbox", { name: /Campus name/ });
  const save = (dialog: HTMLElement) =>
    within(dialog).getByRole("button", { name: "Save name" });
  const route = `PATCH /campuses/${KOCHI.id}`;

  it("has no code field, validates the name and sends it with the version", async () => {
    const api = installFetch();
    api.on(
      route,
      jsonResponse(200, {
        data: { ...KOCHI, name: "Kochi Willingdon Campus", version: 2 },
        meta: {},
      }),
    );
    const { user, dialog, view } = await openRename();
    expect(within(dialog).getAllByRole("textbox")).toHaveLength(1);
    expect(
      within(dialog).getByText("The code KOC stays the same."),
    ).toBeVisible();
    expect(name(dialog)).toHaveValue("Kochi Campus");
    await user.clear(name(dialog));
    await user.click(save(dialog));
    expect(
      within(dialog).getByText("Enter a campus name of up to 200 characters."),
    ).toBeInTheDocument();
    expect(api.callsTo(route)).toHaveLength(0);
    await expectNoA11yViolations(view.container);

    await user.type(name(dialog), "Kochi Willingdon Campus");
    await user.click(save(dialog));
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(api.callsTo(route)[0]!.body).toEqual({
      name: "Kochi Willingdon Campus",
      version: 1,
    });
    expect(toasts.success).toHaveBeenCalledWith("Campus renamed.");
  });

  it("a blank name focuses the field and sends no PATCH", async () => {
    const api = installFetch();
    const { user, dialog } = await openRename();
    await user.clear(name(dialog));
    await user.type(name(dialog), "   ");
    await user.click(save(dialog));
    expect(
      within(dialog).getByText("Enter a campus name of up to 200 characters."),
    ).toBeInTheDocument();
    expect(name(dialog)).toHaveAttribute("aria-invalid", "true");
    await waitFor(() => expect(name(dialog)).toHaveFocus());
    expect(api.calls).toHaveLength(0);
  });

  it("a stale version (409) warns and shows the latest data", async () => {
    const api = installFetch();
    api.on(route, apiError(409, "CONFLICT"));
    const { user, dialog } = await openRename();
    await user.type(name(dialog), " Annexe");
    await user.click(save(dialog));
    await waitFor(() => expect(toasts.warning).toHaveBeenCalled());
    expect(toasts.warning.mock.calls[0]![0]).toMatch(
      /changed it in the meantime/,
    );
    expect(toasts.success).not.toHaveBeenCalled();
    expect(state.refresh).toHaveBeenCalled();
  });

  it("a 404 says the campus is no longer available and re-renders the page", async () => {
    const api = installFetch();
    api.on(route, apiError(404, "NOT_FOUND"));
    const { user, dialog } = await openRename();
    await user.click(save(dialog));
    await waitFor(() =>
      expect(toasts.info).toHaveBeenCalledWith(
        "This campus is no longer available to you.",
      ),
    );
    expect(toasts.success).not.toHaveBeenCalled();
    expect(state.refresh).toHaveBeenCalled();
  });

  it.each([
    [
      "a 403 explains the refusal in the dialog",
      apiError(403, "PERMISSION_DENIED"),
      "You can't rename this campus",
    ],
    [
      "a 422 marks the name",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "name", code: "invalid" }],
      }),
      "Enter a campus name of up to 200 characters.",
    ],
  ])("%s without a success message", async (_label, response, text) => {
    const api = installFetch();
    api.on(route, response);
    const { user, dialog } = await openRename();
    await user.click(save(dialog));
    expect(await within(dialog).findByText(text)).toBeInTheDocument();
    expect(toasts.success).not.toHaveBeenCalled();
    expect(state.refresh).not.toHaveBeenCalled();
    expect(screen.queryByText(/SERVER-/)).toBeNull();
  });
});

// --- Closing the dialogs --------------------------------------------------------

describe("Campus dialogs close without sending", () => {
  const dialogs = [
    {
      label: "Add campus",
      page: list,
      read: ["/campuses", ok(CAMPUS_LIST, 2)] as [string, ReadResult<unknown>],
      trigger: "Add campus",
    },
    {
      label: "Rename campus",
      page: () => detail(),
      read: [`/campuses/${KOCHI.id}`, ok(KOCHI)] as [
        string,
        ReadResult<unknown>,
      ],
      trigger: "Rename",
    },
  ];

  it.each(
    dialogs.flatMap((d) =>
      (["Cancel", "Escape"] as const).map((how) => [d.label, how, d] as const),
    ),
  )("%s closes with %s and returns focus to its button", async (_l, how, d) => {
    const api = installFetch();
    state.reads = [d.read];
    const user = userEvent.setup();
    await show(d.page());
    const trigger = screen.getByRole("button", { name: d.trigger });
    await user.click(trigger);
    const dialog = await screen.findByRole("dialog", { name: d.label });
    await user.type(
      within(dialog).getByRole("textbox", { name: /Campus name/ }),
      " Annexe",
    );
    if (how === "Cancel") {
      await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    } else {
      await waitFor(() =>
        expect(dialog.contains(document.activeElement)).toBe(true),
      );
      await user.keyboard("{Escape}");
    }
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: d.label })).toBeNull(),
    );
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(api.calls).toHaveLength(0);
    expect(state.refresh).not.toHaveBeenCalled();
    expect(toasts.success).not.toHaveBeenCalled();
  });
});

// --- Client rules ---------------------------------------------------------------

describe("Campus rules", () => {
  it("mirror the API: trimmed, uppercase code; collapsed name", () => {
    expect(codeError(" vsk-01 ")).toBeUndefined();
    expect(codeError("-VSK")).toBeDefined();
    expect(codeError("VSK 01")).toBeDefined();
    expect(codeError("A".repeat(33))).toBeDefined();
    expect(nameError("   ")).toBeDefined();
    expect(nameError("Goa  Campus")).toBeUndefined();
    expect(nameError("x".repeat(201))).toBeDefined();
  });
});
