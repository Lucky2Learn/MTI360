import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectHeadingOutline } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import type { ReadResult } from "@/lib/api/server-read";
import type { SessionWire } from "@/lib/api/types";
import { permission, UNRELEASED } from "@/lib/authz/requirements";
import { EXPERIENCE, flattenNavigation, getExperience } from "@/shells";
import { course, IDS, ok } from "@/test/admissions-fixtures";
import { apiError, installFetch, jsonResponse } from "@/test/fetch-mock";
import {
  feeStructure,
  FIN,
  FINANCE_MANAGER,
  FINANCE_OFFICER,
} from "@/test/finance-fixtures";
import { readySession } from "@/test/session-fixtures";

import { TenantFrame } from "../../tenant-frame";

import EditFeeStructurePage from "./[structureId]/edit/page";
import FeeStructurePage from "./[structureId]/page";
import NewFeeStructurePage from "./new/page";
import FeeStructuresPage from "./page";

import type { ReactElement } from "react";

vi.setConfig({ testTimeout: 30_000 });

const TENANT_NAVIGATION = getExperience(EXPERIENCE.TENANT).navigation;

// FIN-02/03 Fee structures (Phase 02-5; ADR-0022; readiness plan §4): the
// released navigation, the server gate, list states, fee_structure.manage-only
// actions, exact paise in the request and the API error mapping.

const state = vi.hoisted(() => ({
  session: null as SessionWire | null,
  reads: [] as [string, ReadResult<unknown>][],
  paths: [] as string[],
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  search: "",
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/app/finance/fee-structure",
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
vi.mock("@/lib/session/server", () => ({
  readTenantSession: () => Promise.resolve(state.session),
  requireReadyTenantSession: (next: string) =>
    state.session
      ? Promise.resolve(state.session)
      : Promise.reject(new Error(`NEXT_REDIRECT /session-ended?next=${next}`)),
}));
vi.mock("@/lib/api/server-read", () => ({
  tenantApiRead: (p: string) => {
    state.paths.push(p);
    const found = state.reads.find(([pattern]) => p.startsWith(pattern));
    return found
      ? Promise.resolve(found[1])
      : Promise.reject(new Error(`unexpected read ${p}`));
  },
}));

beforeEach(() => {
  state.session = readySession({
    permissions: FINANCE_MANAGER,
    all_campuses_allowed: true,
  });
  state.reads = [];
  state.paths = [];
  state.push.mockReset();
  state.replace.mockReset();
  state.refresh.mockReset();
  state.search = "";
});

async function show(
  page: Promise<ReactElement>,
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

const list = (search: Record<string, string> = {}) =>
  FeeStructuresPage({ searchParams: Promise.resolve(search) });
const detail = (id: string = FIN.structure) =>
  FeeStructurePage({ params: Promise.resolve({ structureId: id }) });

describe("Finance navigation (readiness plan §4)", () => {
  it("releases the four Finance-lite pages; Refunds and Reports stay unreleased", () => {
    const byHref = new Map(
      flattenNavigation(TENANT_NAVIGATION).map((item) => [
        item.href,
        item.requirement,
      ]),
    );
    expect(byHref.get("/app/finance/fee-structure")).toEqual(
      permission("fee_structure.read"),
    );
    for (const href of [
      "/app/finance/invoices",
      "/app/finance/payments",
      "/app/finance/outstanding",
    ]) {
      expect(byHref.get(href)).toEqual(permission("invoice.read"));
    }
    expect(byHref.get("/app/finance/refunds")).toBe(UNRELEASED);
    expect(byHref.get("/app/finance/reports")).toBe(UNRELEASED);
  });
});

describe("FIN-02 Fee structures", () => {
  it("needs a session, then fee_structure.read (AUTHZ-01 at the same URL)", async () => {
    state.session = null;
    await expect(list()).rejects.toThrow(
      "NEXT_REDIRECT /session-ended?next=/app/finance/fee-structure",
    );
    state.session = readySession({ permissions: ["lead.read"] });
    await show(list());
    expect(
      screen.getByRole("heading", {
        name: "You don't have access to this page",
      }),
    ).toBeInTheDocument();
    expect(state.paths).toEqual([]);
  });

  it.each(["light", "dark"] as const)(
    "lists structures with exact rupee totals and status text, and passes axe (%s)",
    async (theme) => {
      state.reads.push([
        "/fee-structures",
        ok(
          [
            feeStructure(),
            feeStructure({
              id: FIN.draftStructure,
              name: "GPR fees 2027-28",
              status: "DRAFT",
              total_minor: 26_000_050,
            }),
          ],
          2,
        ),
      ]);
      const { container } = await show(list(), theme);
      const table = screen.getByRole("table", { name: "Fee structures" });
      expect(within(table).getByText("₹2,53,500.00")).toBeInTheDocument();
      expect(within(table).getByText("₹2,60,000.50")).toBeInTheDocument();
      expect(within(table).getByText("Draft")).toBeInTheDocument();
      expect(
        within(table).getByRole("link", { name: "GPR fees 2026-27" }),
      ).toHaveAttribute("href", `/app/finance/fee-structure/${FIN.structure}`);
      expect(
        screen.getByRole("link", { name: "New fee structure" }),
      ).toBeInTheDocument();
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("forwards only known filters and hides New for a finance officer", async () => {
    state.session = readySession({ permissions: FINANCE_OFFICER });
    state.reads.push(["/fee-structures", ok([], 0)]);
    await show(
      list({
        q: "GPR",
        status: "ACTIVE",
        course_id: "not-an-id",
        sort: "drop table",
        tenant_id: "x",
      }),
    );
    const query = new URLSearchParams(state.paths[0]!.split("?")[1]);
    expect(query.get("q")).toBe("GPR");
    expect(query.get("status")).toBe("ACTIVE");
    expect(query.get("sort")).toBe("name");
    expect(query.has("course_id")).toBe(false);
    expect(query.has("tenant_id")).toBe(false);
    expect(
      screen.queryByRole("link", { name: "New fee structure" }),
    ).toBeNull();
    expect(
      screen.getAllByText(
        "Fee structures appear here once your finance team adds them.",
      ).length,
    ).toBeGreaterThan(0);
  });

  it("shows the error state with the support reference", async () => {
    state.reads.push([
      "/fee-structures",
      { kind: "error", reference: "req-7781" },
    ]);
    await show(list());
    expect(
      screen.getByRole("heading", {
        name: "Fee structures couldn't be loaded",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/req-7781/)).toBeInTheDocument();
  });
});

describe("FIN-03 Fee structure", () => {
  it("shows the fee heads and total; activates a draft with its version", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `POST /fee-structures/${FIN.draftStructure}/status`,
      jsonResponse(200, { data: feeStructure(), meta: {} }),
    );
    state.reads.push([
      `/fee-structures/${FIN.draftStructure}`,
      ok(feeStructure({ id: FIN.draftStructure, status: "DRAFT", version: 4 })),
    ]);
    const { container } = await show(detail(FIN.draftStructure));
    const heads = screen.getByRole("table", { name: "Fee heads and amounts" });
    expect(within(heads).getByText("₹1,85,000.00")).toBeInTheDocument();
    expect(within(heads).getByText("₹2,53,500.00")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Edit" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Activate" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent(
      /current active fee structure, if any, is archived/,
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Activate fee structure" }),
    );
    await waitFor(() =>
      expect(
        api.callsTo(`POST /fee-structures/${FIN.draftStructure}/status`),
      ).toHaveLength(1),
    );
    expect(
      api.callsTo(`POST /fee-structures/${FIN.draftStructure}/status`)[0]!.body,
    ).toEqual({ status: "ACTIVE", version: 4 });
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    await expectNoA11yViolations(container);
  });

  it("offers no actions without fee_structure.manage, and none for an archived one", async () => {
    state.session = readySession({ permissions: FINANCE_OFFICER });
    state.reads.push([`/fee-structures/${FIN.structure}`, ok(feeStructure())]);
    await show(detail());
    expect(screen.queryByRole("button", { name: "Archive" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Edit" })).toBeNull();
  });

  it("another institute's or a malformed structure is not found", async () => {
    state.reads.push([
      `/fee-structures/${FIN.structure}`,
      { kind: "not-found" },
    ]);
    await expect(detail()).rejects.toThrow("NEXT_NOT_FOUND");
    await expect(detail("GPR-FEES")).rejects.toThrow("NEXT_NOT_FOUND");
  });
});

describe("FIN-03 Create and edit", () => {
  it("is AUTHZ-01 without fee_structure.manage", async () => {
    state.session = readySession({ permissions: FINANCE_OFFICER });
    await show(NewFeeStructurePage());
    expect(
      screen.getByText("You don't have access to this page"),
    ).toBeInTheDocument();
    expect(state.paths).toEqual([]);
  });

  it("refuses amounts that aren't exact paise and sends integer paise", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      "POST /fee-structures",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "items", code: "duplicate_fee_head" }],
      }),
      jsonResponse(201, {
        data: feeStructure({ id: FIN.draftStructure, status: "DRAFT" }),
        meta: {},
      }),
    );
    state.reads.push(["/courses", ok([course()], 1)]);
    const { container } = await show(NewFeeStructurePage());
    await user.click(screen.getByRole("button", { name: "Create draft" }));
    expect(await screen.findByText("Choose the course.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Course/ }));
    await user.click(await screen.findByRole("option", { name: /GPR/ }));
    await user.type(
      screen.getByRole("textbox", { name: /Name/ }),
      "GPR fees 2026-27",
    );
    await user.type(
      screen.getByRole("textbox", { name: /Amount 1/ }),
      "1,85,000.005",
    );
    await user.type(
      screen.getByRole("textbox", { name: /Fee head 2/ }),
      "Hostel",
    );
    await user.type(screen.getByRole("textbox", { name: /Amount 2/ }), "60000");
    await user.click(screen.getByRole("button", { name: "Create draft" }));
    expect(
      await screen.findByText(
        "Enter an amount in rupees, e.g. 25000 or 1,25,000.50.",
      ),
    ).toBeInTheDocument();
    expect(api.callsTo("POST /fee-structures")).toHaveLength(0);

    await user.clear(screen.getByRole("textbox", { name: /Amount 1/ }));
    await user.type(
      screen.getByRole("textbox", { name: /Amount 1/ }),
      "1,85,000.50",
    );
    expect(screen.getByText("₹2,45,000.50")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create draft" }));
    expect(
      await screen.findByText("Use each fee head once."),
    ).toBeInTheDocument();
    expect(api.callsTo("POST /fee-structures")[0]!.body).toEqual({
      course_id: IDS.gpr,
      name: "GPR fees 2026-27",
      items: [
        { fee_head: "Tuition", amount_minor: 18_500_050 },
        { fee_head: "Hostel", amount_minor: 6_000_000 },
      ],
    });
    expect(container.textContent).not.toContain("SERVER-");

    await user.click(screen.getByRole("button", { name: "Create draft" }));
    await waitFor(() =>
      expect(state.push).toHaveBeenCalledWith(
        `/app/finance/fee-structure/${FIN.draftStructure}`,
      ),
    );
  });

  it("edits a draft with its version; an active structure explains why it can't be edited", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `PATCH /fee-structures/${FIN.draftStructure}`,
      apiError(409, "CONFLICT"),
    );
    state.reads.push([
      `/fee-structures/${FIN.draftStructure}`,
      ok(feeStructure({ id: FIN.draftStructure, status: "DRAFT", version: 5 })),
    ]);
    await show(
      EditFeeStructurePage({
        params: Promise.resolve({ structureId: FIN.draftStructure }),
      }),
    );
    expect(screen.getByRole("textbox", { name: /Amount 1/ })).toHaveValue(
      "185000",
    );
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(
      await screen.findByText("This fee structure changed"),
    ).toBeInTheDocument();
    expect(
      api.callsTo(`PATCH /fee-structures/${FIN.draftStructure}`)[0]!.body,
    ).toMatchObject({ version: 5, name: "GPR fees 2026-27" });

    state.reads = [[`/fee-structures/${FIN.structure}`, ok(feeStructure())]];
    await show(
      EditFeeStructurePage({
        params: Promise.resolve({ structureId: FIN.structure }),
      }),
    );
    expect(
      screen.getByText("This fee structure can't be edited"),
    ).toBeInTheDocument();
  });
});
