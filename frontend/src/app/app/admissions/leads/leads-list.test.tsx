import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { toastQueue } from "@/design-system/components";
import { expectHeadingOutline } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import type { ReadResult } from "@/lib/api/server-read";
import type { SessionWire } from "@/lib/api/types";
import { COUNSELLOR, IDS, leadItem, ok } from "@/test/admissions-fixtures";
import { apiError, installFetch, jsonResponse } from "@/test/fetch-mock";
import { readySession } from "@/test/session-fixtures";

import { TenantFrame } from "../../tenant-frame";

import LeadsPage from "./page";

vi.setConfig({ testTimeout: 30_000 });

// GROW-08 list and ADM-02 board (Phase 02-1; blueprint §21-§23): server gate,
// list and board views of one route, URL filters (IDs and enums only), the
// "Move to…" menu that calls the server and never moves a card first, the
// mobile one-column selector, and empty / error states.

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
  usePathname: () => "/app/admissions/leads",
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
  tenantApiRead: (path: string) => {
    state.paths.push(path);
    const found = state.reads.find(([pattern]) => path.includes(pattern));
    return found
      ? Promise.resolve(found[1])
      : Promise.reject(new Error(`unexpected read ${path}`));
  },
}));

beforeEach(() => {
  state.session = readySession({ permissions: COUNSELLOR });
  state.reads = [["/courses", ok([], 0)]];
  state.paths = [];
  state.push.mockReset();
  state.replace.mockReset();
  state.refresh.mockReset();
  state.search = "";
});

async function show(
  params: Record<string, string> = {},
  theme: "light" | "dark" = "light",
) {
  state.search = new URLSearchParams(params).toString();
  const element = await LeadsPage({ searchParams: Promise.resolve(params) });
  document.documentElement.dataset.theme = theme;
  return render(
    <ThemeProvider>
      <TenantFrame session={state.session!} showUnreleased={false}>
        {element}
      </TenantFrame>
    </ThemeProvider>,
  );
}

describe("gate", () => {
  it("session first, then lead.read", async () => {
    state.session = null;
    await expect(
      LeadsPage({ searchParams: Promise.resolve({}) }),
    ).rejects.toThrow(
      "NEXT_REDIRECT /session-ended?next=/app/admissions/leads",
    );
    state.session = readySession({ permissions: ["course.read"] });
    await show();
    expect(
      screen.getByText("You don't have access to this page"),
    ).toBeInTheDocument();
  });
});

describe("list view", () => {
  it.each(["light", "dark"] as const)(
    "shows open leads with contact, owner, status and an overdue marker (%s)",
    async (theme) => {
      state.reads.unshift([
        "/leads?",
        ok([leadItem({ overdue_follow_ups: 1 })], 1),
      ]);
      const { container } = await show({}, theme);
      const table = screen.getByRole("table", { name: "Leads" });
      expect(
        within(table).getByRole("link", { name: "Arjun Nair" }),
      ).toHaveAttribute("href", `/app/admissions/leads/${IDS.arjun}`);
      expect(within(table).getByText("+91 90000 10001")).toBeInTheDocument();
      expect(within(table).getByText("Ravi Menon")).toBeInTheDocument();
      expect(within(table).getByText("Overdue")).toBeInTheDocument();
      // Without a status filter the server is asked for the open statuses.
      const query = state.paths.find((p) => p.startsWith("/leads?"))!;
      expect(new URLSearchParams(query.split("?")[1]).getAll("status")).toEqual(
        ["NEW", "CONTACTED", "QUALIFIED", "COUNSELLING", "INTERESTED"],
      );
      expect(
        screen.getByRole("link", { name: "New lead" }),
      ).toBeInTheDocument();
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("drops unknown URL values and never sends personal data except the search term", async () => {
    state.reads.unshift(["/leads?", ok([], 0)]);
    await show({
      status: "ENROLLED",
      owner: "someone@example.com",
      campus: "x",
      source: "TELEPATHY",
      q: "Arjun",
    });
    const query = new URLSearchParams(
      state.paths.find((p) => p.startsWith("/leads?"))!.split("?")[1],
    );
    expect(query.get("owner")).toBeNull();
    expect(query.get("campus")).toBeNull();
    expect(query.get("source")).toBeNull();
    expect(query.get("q")).toBe("Arjun");
    expect(query.getAll("status")).toHaveLength(5);
  });

  it("filters update the URL; quick filters are links to URL states", async () => {
    const user = userEvent.setup();
    state.reads.unshift(["/leads?", ok([leadItem()], 1)]);
    await show();
    const quick = screen.getByRole("navigation", { name: "Quick filters" });
    expect(
      within(quick).getByRole("link", { name: "My leads" }),
    ).toHaveAttribute("href", "/app/admissions/leads?owner=me");
    await user.click(screen.getAllByRole("button", { name: /Source/ })[0]!);
    await user.click(await screen.findByRole("option", { name: "Walk-in" }));
    expect(state.replace).toHaveBeenCalledWith(
      "/app/admissions/leads?source=WALK_IN",
      { scroll: false },
    );
  });

  it("empty states: first-lead call to action, or filtered-empty", async () => {
    state.reads.unshift(["/leads?", ok([], 0)]);
    await show();
    expect(
      screen.getAllByText("Add your first enquiry to start the pipeline.")[0],
    ).toBeInTheDocument();
    await show({ owner: "unassigned" });
    expect(
      screen.getAllByText("No leads match these filters")[0],
    ).toBeInTheDocument();
  });

  it("a failed read shows the error state with its reference", async () => {
    state.reads.unshift(["/leads?", { kind: "error", reference: "req-9" }]);
    await show();
    expect(screen.getByText("Leads couldn't be loaded")).toBeInTheDocument();
    expect(screen.getByText(/req-9/)).toBeInTheDocument();
  });
});

describe("board view (ADM-02)", () => {
  function boardReads() {
    state.reads.unshift(
      ["status=NEW", ok([leadItem()], 30)],
      ["status=CONTACTED", ok([], 0)],
      ["status=QUALIFIED", ok([], 0)],
      ["status=COUNSELLING", ok([], 0)],
      ["status=INTERESTED", ok([], 0)],
    );
  }

  it.each(["light", "dark"] as const)(
    "shows one column per open status with totals (%s)",
    async (theme) => {
      boardReads();
      const { container } = await show({ view: "board" }, theme);
      for (const name of [
        "New",
        "Contacted",
        "Qualified",
        "Counselling",
        "Ready to apply",
      ]) {
        expect(
          screen.getByRole("region", { name: new RegExp(`^${name}`) }),
        ).toBeInTheDocument();
      }
      const column = screen.getByRole("region", { name: /^New/ });
      expect(within(column).getByText("30 leads")).toBeInTheDocument();
      expect(
        within(column).getByRole("link", { name: "View all 30 in the list" }),
      ).toHaveAttribute("href", "/app/admissions/leads?view=list&status=NEW");
      // Mobile: one column at a time, chosen with a selector.
      expect(
        screen.getByRole("button", { name: /Pipeline stage/ }),
      ).toBeInTheDocument();
      expect(
        state.paths.filter((p) => p.includes("sort=-updated_at")),
      ).toHaveLength(5);
      await expectNoA11yViolations(container);
    },
  );

  it("Move to… calls the server with the version and never moves the card first", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `POST /leads/${IDS.arjun}/transition`,
      jsonResponse(200, { data: {} }),
    );
    boardReads();
    await show({ view: "board" });
    const column = screen.getByRole("region", { name: /^New/ });
    await user.click(
      within(column).getByRole("button", { name: "Actions for Arjun Nair" }),
    );
    await user.click(await screen.findByRole("menuitem", { name: "Move to…" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Move Arjun Nair to…",
    });
    await user.click(
      within(dialog).getByRole("button", { name: /New status/ }),
    );
    await user.click(await screen.findByRole("option", { name: "Contacted" }));
    // Not moved on screen before the server answers.
    expect(within(column).getByText("Arjun Nair")).toBeInTheDocument();
    await user.click(
      within(dialog).getByRole("button", { name: "Save status" }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(api.callsTo(`POST /leads/${IDS.arjun}/transition`)[0]!.body).toEqual(
      {
        to_status: "CONTACTED",
        reason: null,
        duplicate_of_lead_id: null,
        version: 3,
      },
    );
  });

  it("a stale card refreshes with a notice instead of failing silently", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(`POST /leads/${IDS.arjun}/transition`, apiError(409, "CONFLICT"));
    boardReads();
    await show({ view: "board" });
    await user.click(
      screen.getAllByRole("button", { name: "Actions for Arjun Nair" })[0]!,
    );
    await user.click(await screen.findByRole("menuitem", { name: "Move to…" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(
      within(dialog).getByRole("button", { name: /New status/ }),
    );
    await user.click(await screen.findByRole("option", { name: "Qualified" }));
    await user.click(
      within(dialog).getByRole("button", { name: "Save status" }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(
      toastQueue.visibleToasts.some((t) =>
        t.content.title.startsWith("This lead changed"),
      ),
    ).toBe(true);
  });

  it("counsellors get no Assign… and only server-allowed moves", async () => {
    const user = userEvent.setup();
    boardReads();
    await show({ view: "board" });
    await user.click(
      screen.getAllByRole("button", { name: "Actions for Arjun Nair" })[0]!,
    );
    const menu = await screen.findByRole("menu");
    expect(
      within(menu)
        .getAllByRole("menuitem")
        .map((item) => item.textContent),
    ).toEqual(["Open lead", "Move to…"]);
  });
});
