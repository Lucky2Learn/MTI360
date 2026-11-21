import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import { groupPermissions, moduleLabel } from "@/features/roles/labels";
import type { ReadResult } from "@/lib/api/server-read";
import type { SessionWire } from "@/lib/api/types";
import { ok } from "@/test/admissions-fixtures";
import { CAMPUSES, readySession } from "@/test/session-fixtures";
import {
  CAMPUS_LIST,
  member,
  MEMBER_IDS,
  OWNER_PERMISSIONS,
  PERMISSION_CATALOGUE,
  role,
  ROLES,
} from "@/test/tenant-admin-fixtures";

import TenantLoading from "../../loading";
import { TenantFrame } from "../../tenant-frame";
import UserDetailPage from "../users/[memberId]/page";

import RoleDetailPage from "./[roleId]/page";
import RolesPage from "./page";

import type { ReactElement } from "react";

vi.setConfig({ testTimeout: 30_000 });

// ADMIN-07 Roles & Permissions (02-C over the T01-08 API, read-only): the
// server gate, list and detail states, system/custom labelling, member
// counts, the permission catalogue grouped by module with granted and
// ungranted permissions, and the links to and from User detail. All API
// reads are scripted; nothing is written.

const state = vi.hoisted(() => ({
  session: null as SessionWire | null,
  reads: [] as [string, ReadResult<unknown>][],
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/app/administration/roles",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
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

const owner = (overrides: Partial<SessionWire> = {}) =>
  readySession({
    permissions: OWNER_PERMISSIONS,
    all_campuses_allowed: true,
    campus_options: [CAMPUSES.kochi, CAMPUSES.vizag],
    ...overrides,
  });

beforeEach(() => {
  state.session = owner();
  state.reads = [];
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

const list = () => RolesPage();
const detail = (id: string = MEMBER_IDS.counsellorRole) =>
  RoleDetailPage({ params: Promise.resolve({ roleId: id }) });

const CUSTOM = role({
  id: "0192a1b2-c3d4-7e5f-8a6b-7c8d9e0f1b04",
  name: "Placement coordinator",
  description: null,
  is_system: false,
  permissions: ["member.read"],
  member_count: 0,
});

function detailReads(target = role()) {
  state.reads = [
    [`/roles/${target.id}`, ok(target)],
    ["/permissions", ok(PERMISSION_CATALOGUE, PERMISSION_CATALOGUE.length)],
  ];
}

const accessDenied = () =>
  screen.getByRole("heading", { name: "You don't have access to this page" });

// --- ADMIN-07 list --------------------------------------------------------------

describe("ADMIN-07 Roles", () => {
  it("needs a session first, then role.read (AUTHZ-01 at the same URL)", async () => {
    state.session = null;
    await expect(list()).rejects.toThrow(
      "NEXT_REDIRECT /session-ended?next=/app/administration/roles",
    );
    state.session = readySession({ permissions: ["member.read"] });
    await show(list());
    expect(accessDenied()).toBeInTheDocument();
  });

  it.each(["light", "dark"] as const)(
    "lists roles with type, member and permission counts, and passes axe (%s)",
    async (theme) => {
      state.reads = [["/roles", ok([...ROLES, CUSTOM], 4)]];
      const { container } = await show(list(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "Roles & Permissions" }),
      ).toBeInTheDocument();
      const table = screen.getByRole("table", { name: "Roles" });

      const counsellor = within(table).getByRole("row", { name: /Counsellor/ });
      expect(within(counsellor).getByText("System role")).toBeInTheDocument();
      expect(within(counsellor).getByText("4 members")).toBeInTheDocument();
      expect(within(counsellor).getByText("2 permissions")).toBeInTheDocument();
      expect(
        within(counsellor).getByText("Works leads and applications."),
      ).toBeInTheDocument();

      const custom = within(table).getByRole("row", {
        name: /Placement coordinator/,
      });
      expect(within(custom).getByText("Custom role")).toBeInTheDocument();
      expect(within(custom).getByText("0 members")).toBeInTheDocument();
      expect(within(custom).getByText("1 permission")).toBeInTheDocument();
      expect(
        within(table).getByRole("row", { name: /Finance manager/ }),
      ).toHaveTextContent("1 member");

      expect(
        within(table).getByRole("link", { name: "Placement coordinator" }),
      ).toHaveAttribute("href", `/app/administration/roles/${CUSTOM.id}`);
      // Read-only: no create, edit or delete.
      expect(
        screen.queryByRole("button", { name: /create|new role|edit|delete/i }),
      ).toBeNull();
      await expectNoA11yViolations(container);
    },
  );

  it("turns rows into cards below tablet and hides the permission count column on mobile", async () => {
    state.reads = [["/roles", ok(ROLES, 3)]];
    await show(list());
    const cards = screen.getByRole("list", { name: "Roles" });
    expect(cards.parentElement).toHaveClass("tablet:hidden");
    expect(within(cards).getAllByRole("listitem")).toHaveLength(3);
    expect(
      screen.getByRole("columnheader", { name: "Permissions" }),
    ).toHaveClass("hidden", "tablet:table-cell");
  });

  it("explains an empty role list", async () => {
    state.reads = [["/roles", ok([], 0)]];
    await show(list());
    expect(screen.getAllByText("No roles yet").length).toBeGreaterThan(0);
  });

  it("shows the error state with the reference, and AUTHZ-01 when the API refuses", async () => {
    state.reads = [["/roles", { kind: "error", reference: "req-4410" }]];
    const { unmount } = await show(list());
    expect(
      screen.getByRole("heading", { name: "Roles couldn't be loaded" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/req-4410/)).toBeInTheDocument();
    unmount();
    state.reads = [["/roles", { kind: "denied" }]];
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

// --- ADMIN-07 detail ------------------------------------------------------------

describe("ADMIN-07 Role detail", () => {
  it("needs role.read; another institute's role or a malformed ID is not found", async () => {
    state.session = owner({ permissions: ["member.read"] });
    await show(detail());
    expect(accessDenied()).toBeInTheDocument();

    state.session = owner();
    state.reads = [
      [`/roles/${MEMBER_IDS.counsellorRole}`, { kind: "not-found" }],
      ["/permissions", ok(PERMISSION_CATALOGUE)],
    ];
    await expect(detail()).rejects.toThrow("NEXT_NOT_FOUND");
    await expect(detail("not-a-role")).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("sends an ended session to sign in, and shows the error state or AUTHZ-01", async () => {
    state.reads = [
      [`/roles/${MEMBER_IDS.counsellorRole}`, { kind: "unauthenticated" }],
      ["/permissions", ok(PERMISSION_CATALOGUE)],
    ];
    await expect(detail()).rejects.toThrow(
      `NEXT_REDIRECT /session-ended?reason=ended&next=${encodeURIComponent(
        `/app/administration/roles/${MEMBER_IDS.counsellorRole}`,
      )}`,
    );

    state.reads[0] = [
      `/roles/${MEMBER_IDS.counsellorRole}`,
      { kind: "error", reference: "req-5521" },
    ];
    const { unmount } = await show(detail());
    expect(
      screen.getByRole("heading", { name: "This role couldn't be loaded" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/req-5521/)).toBeInTheDocument();
    unmount();

    state.reads[0] = [
      `/roles/${MEMBER_IDS.counsellorRole}`,
      { kind: "denied" },
    ];
    await show(detail());
    expect(accessDenied()).toBeInTheDocument();
  });

  it.each(["light", "dark"] as const)(
    "groups the catalogue by module and marks granted and ungranted permissions, and passes axe (%s)",
    async (theme) => {
      detailReads();
      const { container } = await show(detail(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "Counsellor" }),
      ).toBeInTheDocument();
      expect(screen.getAllByText("System role").length).toBeGreaterThan(0);
      expect(
        screen.getByText(/Its name and permissions can't be changed/),
      ).toBeInTheDocument();

      const permissions = screen.getByRole("region", { name: "Permissions" });
      expect(
        within(permissions).getByText("2 permissions granted, of 6 available."),
      ).toBeInTheDocument();
      // Modules from the API, in label order.
      expect(
        within(permissions)
          .getAllByRole("heading", { level: 3 })
          .map((heading) => heading.textContent),
      ).toEqual(["Access", "Finance", "Identity", "Institute", "Leads"]);

      const leads = within(permissions).getByRole("region", { name: "Leads" });
      expect(within(leads).getByText("2 of 2 granted")).toBeInTheDocument();
      const add = within(leads).getByText("Add leads").closest("li")!;
      expect(within(add).getByText("Granted")).toBeInTheDocument();
      expect(within(add).getByText("lead.create")).toBeInTheDocument();
      expect(add).toHaveTextContent("Per campus");

      const identity = within(permissions).getByRole("region", {
        name: "Identity",
      });
      expect(within(identity).getByText("0 of 1 granted")).toBeInTheDocument();
      const members = within(identity).getByText("View members").closest("li")!;
      expect(within(members).getByText("Not granted")).toBeInTheDocument();
      expect(within(members).queryByText("Granted")).toBeNull();
      expect(members).toHaveTextContent("Institute-wide");

      const summary = screen.getByRole("complementary", { name: "Summary" });
      expect(within(summary).getByText("4 members")).toBeInTheDocument();
      expect(
        within(summary).getByRole("link", { name: "View users" }),
      ).toHaveAttribute("href", "/app/administration/users");
      expect(screen.queryByRole("button", { name: /edit|delete/i })).toBeNull();
      await expectNoA11yViolations(container);
    },
  );

  it("labels a custom role and hides the users link without member.read", async () => {
    state.session = owner({ permissions: ["role.read"] });
    detailReads(CUSTOM);
    await show(detail(CUSTOM.id));
    expect(
      screen.getByRole("heading", { level: 1, name: "Placement coordinator" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Custom role")).toBeInTheDocument();
    expect(screen.getByText("Created by your institute.")).toBeInTheDocument();
    expect(screen.queryByText(/can't be changed/)).toBeNull();
    const summary = screen.getByRole("complementary", { name: "Summary" });
    expect(within(summary).getByText("0 members")).toBeInTheDocument();
    expect(within(summary).queryByRole("link")).toBeNull();
  });

  it("lists a held permission the catalogue doesn't describe by its code", async () => {
    detailReads(ROLES[2]);
    await show(detail(MEMBER_IDS.financeRole));
    const unlisted = screen.getByRole("region", {
      name: "Not in the permission catalogue",
    });
    expect(within(unlisted).getByText("payment.record")).toBeInTheDocument();
    const finance = screen.getByRole("region", { name: "Finance" });
    expect(within(finance).getByText("1 of 1 granted")).toBeInTheDocument();
  });

  it("still shows the role, by permission code, when the catalogue can't be loaded", async () => {
    state.reads = [
      [`/roles/${MEMBER_IDS.counsellorRole}`, ok(role())],
      ["/permissions", { kind: "error", reference: "req-6630" }],
    ];
    await show(detail());
    expect(
      screen.getByText("Permission details couldn't be loaded"),
    ).toBeInTheDocument();
    expect(screen.getByText(/req-6630/)).toBeInTheDocument();
    const codes = screen.getByRole("list", { name: "Granted permissions" });
    expect(within(codes).getByText("lead.read")).toBeInTheDocument();
    expect(within(codes).getByText("lead.create")).toBeInTheDocument();
  });

  it("says when a role has no permissions", async () => {
    state.reads = [
      [`/roles/${CUSTOM.id}`, ok({ ...CUSTOM, permissions: [] })],
      ["/permissions", { kind: "error", reference: null }],
    ];
    await show(detail(CUSTOM.id));
    expect(
      screen.getByText("This role has no permissions."),
    ).toBeInTheDocument();
  });
});

// --- Links from User detail -------------------------------------------------------

describe("User detail → role", () => {
  function userReads() {
    state.reads = [
      [`/members/${MEMBER_IDS.rahul}`, ok(member())],
      ["/roles", ok(ROLES)],
      ["/campuses", ok(CAMPUS_LIST)],
    ];
  }
  const user = () =>
    UserDetailPage({ params: Promise.resolve({ memberId: MEMBER_IDS.rahul }) });

  it("links a held role to its ADMIN-07 page with role.read", async () => {
    userReads();
    await show(user());
    const roles = screen
      .getByRole("heading", { level: 2, name: "Roles" })
      .closest("section")!;
    expect(
      within(roles).getByRole("link", { name: "Counsellor" }),
    ).toHaveAttribute(
      "href",
      `/app/administration/roles/${MEMBER_IDS.counsellorRole}`,
    );
  });

  it("shows the role name without a link without role.read", async () => {
    state.session = owner({ permissions: ["member.read"] });
    state.reads = [[`/members/${MEMBER_IDS.rahul}`, ok(member())]];
    await show(user());
    const roles = screen
      .getByRole("heading", { level: 2, name: "Roles" })
      .closest("section")!;
    expect(within(roles).getByText("Counsellor")).toBeInTheDocument();
    expect(within(roles).queryByRole("link")).toBeNull();
  });
});

// --- Helpers --------------------------------------------------------------------

describe("Permission grouping", () => {
  it("formats module slugs from the API without inventing names", () => {
    expect(moduleLabel("platform_identity")).toBe("Platform identity");
    expect(moduleLabel("leads")).toBe("Leads");
    expect(moduleLabel("")).toBe("Other");
  });

  it("keeps catalogue order within a module and counts what is granted", () => {
    const { groups, unlisted } = groupPermissions(PERMISSION_CATALOGUE, [
      "lead.read",
      "ghost.code",
    ]);
    const leads = groups.find((group) => group.module === "leads")!;
    expect(leads.permissions.map((p) => [p.code, p.granted])).toEqual([
      ["lead.create", false],
      ["lead.read", true],
    ]);
    expect(leads.granted).toBe(1);
    expect(unlisted).toEqual(["ghost.code"]);
  });
});
