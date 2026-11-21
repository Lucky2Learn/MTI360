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
import { memberListQuery } from "@/features/members/query";
import type { ReadResult } from "@/lib/api/server-read";
import type { SessionWire } from "@/lib/api/types";
import { ok } from "@/test/admissions-fixtures";
import {
  apiError,
  installFetch,
  jsonResponse,
  noContent,
} from "@/test/fetch-mock";
import { CAMPUSES, readySession } from "@/test/session-fixtures";
import {
  CAMPUS_LIST,
  member,
  MEMBER_IDS,
  OWNER_PERMISSIONS,
  ROLES,
  selfMember,
} from "@/test/tenant-admin-fixtures";

import { TenantFrame } from "../../tenant-frame";

import UserDetailPage from "./[memberId]/page";
import UsersPage from "./page";

import type { ReactElement } from "react";

vi.setConfig({ testTimeout: 30_000 });

// ADMIN-05 Users and ADMIN-06 User detail (02-C over the T01-08 API): the
// server gate, list and detail states, the invitation form, role and campus
// changes, status actions, self-protection in the UI and the handling of
// 403 / 409 / 422 (never a success message for a refusal). All API calls are
// scripted: no invitation is sent and no database is touched.

const state = vi.hoisted(() => ({
  session: null as SessionWire | null,
  reads: [] as [string, ReadResult<unknown>][],
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  search: "",
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/app/administration/users",
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
    const found = state.reads.find(([pattern]) => path.startsWith(pattern));
    return found
      ? Promise.resolve(found[1])
      : Promise.reject(new Error(`unexpected read ${path}`));
  },
}));

// Toast spies are created per test (restoreMocks: true) and render nothing,
// so no toast outlives its test in the global queue.
const toasts = {} as Record<
  "success" | "warning" | "error" | "info",
  MockInstance<(typeof toast)["success"]>
>;

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
  state.push.mockReset();
  state.replace.mockReset();
  state.refresh.mockReset();
  state.search = "";
  for (const tone of ["success", "warning", "error", "info"] as const) {
    toasts[tone] = vi.spyOn(toast, tone).mockReturnValue("toast");
  }
});

afterEach(() => {
  vi.unstubAllGlobals();
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

const list = (params: Record<string, string> = {}) =>
  UsersPage({ searchParams: Promise.resolve(params) });
const detail = (id: string = MEMBER_IDS.rahul) =>
  UserDetailPage({ params: Promise.resolve({ memberId: id }) });

function detailReads(target = member()) {
  state.reads = [
    [`/members/${target.id}`, ok(target)],
    ["/roles", ok(ROLES)],
    ["/campuses", ok(CAMPUS_LIST)],
  ];
}

const RAHUL = member();
const PRIYA = member({
  id: MEMBER_IDS.priya,
  user: {
    display_name: "Priya Nair",
    email: "priya.nair@coastal-maritime.example",
  },
  status: "INVITED",
  campus_scope: "ALL",
  campus_ids: [],
  roles: [],
  joined_at: null,
  version: 1,
});

// --- ADMIN-05 -------------------------------------------------------------------

describe("ADMIN-05 Users", () => {
  it("needs a session first, then member.read (AUTHZ-01 at the same URL)", async () => {
    state.session = null;
    await expect(list()).rejects.toThrow(
      "NEXT_REDIRECT /session-ended?next=/app/administration/users",
    );
    state.session = readySession({ permissions: ["lead.read"] });
    await show(list());
    expect(
      screen.getByRole("heading", {
        name: "You don't have access to this page",
      }),
    ).toBeInTheDocument();
  });

  it.each(["light", "dark"] as const)(
    "lists members with a readable status and marks your own row, and passes axe (%s)",
    async (theme) => {
      state.reads = [["/members", ok([selfMember(), RAHUL, PRIYA], 3)]];
      const { container } = await show(list(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "Users" }),
      ).toBeInTheDocument();
      const table = screen.getByRole("table", { name: "Members" });
      expect(within(table).getByText("Rahul Menon")).toBeInTheDocument();
      expect(
        within(screen.getByRole("row", { name: /Priya Nair/ })).getByText(
          "Invited",
        ),
      ).toBeInTheDocument();
      expect(within(table).getAllByText("Active")).toHaveLength(2);
      expect(within(table).getByText("You")).toBeInTheDocument();
      expect(
        within(table).getByRole("link", { name: "Priya Nair" }),
      ).toHaveAttribute(
        "href",
        `/app/administration/users/${MEMBER_IDS.priya}`,
      );
      expect(screen.getByText("3 members")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Invite member" }),
      ).toBeInTheDocument();
      await expectNoA11yViolations(container);
    },
  );

  it("offers no invitation without member.invite", async () => {
    state.session = owner({ permissions: ["member.read"] });
    state.reads = [["/members", ok([RAHUL], 1)]];
    await show(list());
    expect(screen.queryByRole("button", { name: "Invite member" })).toBeNull();
  });

  it("explains an empty institute, a filtered-empty list and a page past the end", async () => {
    state.reads = [["/members", ok([], 0)]];
    const { unmount } = await show(list());
    expect(screen.getAllByText("No members yet").length).toBeGreaterThan(0);
    expect(
      screen.getAllByRole("button", { name: "Invite member" }).length,
    ).toBeGreaterThan(0);
    unmount();

    state.search = "q=zz&status=SUSPENDED";
    const second = await show(list({ q: "zz", status: "SUSPENDED" }));
    expect(
      screen.getAllByText("No members match these filters").length,
    ).toBeGreaterThan(0);
    second.unmount();

    state.search = "offset=50";
    state.reads = [
      [
        "/members",
        { kind: "ok", data: [], page: { limit: 25, offset: 50, total: 3 } },
      ],
    ];
    await show(list({ offset: "50" }));
    expect(
      screen.getAllByText("No members on this page").length,
    ).toBeGreaterThan(0);
  });

  it("shows the error state with the reference, and AUTHZ-01 when the API refuses", async () => {
    state.reads = [["/members", { kind: "error", reference: "req-7781" }]];
    const { unmount } = await show(list());
    expect(
      screen.getByRole("heading", { name: "Members couldn't be loaded" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/req-7781/)).toBeInTheDocument();
    unmount();
    state.reads = [["/members", { kind: "denied" }]];
    await show(list());
    expect(
      screen.getByRole("heading", {
        name: "You don't have access to this page",
      }),
    ).toBeInTheDocument();
  });

  it("forwards only known filters and sorts to the API", () => {
    expect(
      memberListQuery({
        q: "  rahul ",
        status: "REVOKED",
        sort: "-created_at",
        offset: "25",
        tenant_id: "another",
      }),
    ).toBe("q=rahul&status=REVOKED&sort=-created_at&limit=25&offset=25");
    expect(memberListQuery({ status: "OWNER", sort: "password" })).toBe(
      "sort=display_name&limit=25&offset=0",
    );
  });
});

// --- Invite member ----------------------------------------------------------------

describe("Invite member", () => {
  async function openInvite(api: ReturnType<typeof installFetch>) {
    api.on("GET /roles", jsonResponse(200, { data: ROLES, meta: {} }));
    api.on("GET /campuses", jsonResponse(200, { data: CAMPUS_LIST, meta: {} }));
    state.reads = [["/members", ok([RAHUL], 1)]];
    const user = userEvent.setup();
    const view = await show(list());
    await user.click(screen.getByRole("button", { name: "Invite member" }));
    const dialog = await screen.findByRole("dialog", { name: "Invite member" });
    await within(dialog).findByRole("checkbox", { name: "Counsellor" });
    return { user, dialog, view };
  }

  it("validates before sending: email, name and at least one chosen campus", async () => {
    const api = installFetch();
    const { user, dialog } = await openInvite(api);
    await user.click(
      within(dialog).getByRole("radio", { name: /Selected campuses/ }),
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Send invitation" }),
    );
    expect(
      within(dialog).getByText(
        "Enter an email address like name@institute.edu.",
      ),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText("Enter the person's name."),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText("Choose at least one campus."),
    ).toBeInTheDocument();
    expect(api.callsTo("POST /members/invitations")).toHaveLength(0);
  });

  it("offers only grantable roles, sends roles and campuses, and says a new invitation is being emailed", async () => {
    const api = installFetch();
    api.on(
      "POST /members/invitations",
      jsonResponse(201, {
        data: { member: PRIYA, account: "new" },
        meta: {},
      }),
    );
    const { user, dialog, view } = await openInvite(api);
    const finance = within(dialog).getByRole("checkbox", {
      name: /Finance manager/,
    });
    expect(finance).toBeDisabled();
    expect(
      within(dialog).getByText("Includes access you don't have."),
    ).toBeInTheDocument();
    await expectNoA11yViolations(view.container);

    await user.type(
      within(dialog).getByRole("textbox", { name: /Email/ }),
      " priya.nair@coastal-maritime.example ",
    );
    await user.type(
      within(dialog).getByRole("textbox", { name: /Full name/ }),
      "Priya Nair",
    );
    await user.click(
      within(dialog).getByRole("checkbox", { name: "Counsellor" }),
    );
    await user.click(
      within(dialog).getByRole("radio", { name: /Selected campuses/ }),
    );
    await user.click(
      within(dialog).getByRole("checkbox", {
        name: "Visakhapatnam Campus (VTZ)",
      }),
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Send invitation" }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(api.callsTo("POST /members/invitations")[0]!.body).toEqual({
      email: "priya.nair@coastal-maritime.example",
      display_name: "Priya Nair",
      role_ids: [MEMBER_IDS.counsellorRole],
      campus_scope: "SELECTED",
      campus_ids: [CAMPUSES.vizag.id],
    });
    expect(toasts.success).toHaveBeenCalledWith(
      "An invitation is being emailed to priya.nair@coastal-maritime.example.",
    );
  });

  it("says when an existing account was invited unchanged", async () => {
    const api = installFetch();
    api.on(
      "POST /members/invitations",
      jsonResponse(201, {
        data: { member: PRIYA, account: "existing" },
        meta: {},
      }),
    );
    const { user, dialog } = await openInvite(api);
    await user.type(
      within(dialog).getByRole("textbox", { name: /Email/ }),
      "priya.nair@coastal-maritime.example",
    );
    await user.type(
      within(dialog).getByRole("textbox", { name: /Full name/ }),
      "Priya Nair",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Send invitation" }),
    );
    await waitFor(() => expect(toasts.success).toHaveBeenCalled());
    expect(toasts.success.mock.calls[0]![0]).toMatch(
      /already has an MTI 360 account/,
    );
    expect(api.callsTo("POST /members/invitations")[0]!.body).toMatchObject({
      role_ids: [],
      campus_scope: "ALL",
      campus_ids: [],
    });
  });

  it.each([
    [apiError(409, "CONFLICT"), "This person wasn't invited"],
    [apiError(403, "PERMISSION_DENIED"), "You can't make this change"],
  ])(
    "keeps the dialog open on a refusal, without a success message",
    async (response, title) => {
      const api = installFetch();
      api.on("POST /members/invitations", response);
      const { user, dialog } = await openInvite(api);
      await user.type(
        within(dialog).getByRole("textbox", { name: /Email/ }),
        "rahul.menon@coastal-maritime.example",
      );
      await user.type(
        within(dialog).getByRole("textbox", { name: /Full name/ }),
        "Rahul Menon",
      );
      await user.click(
        within(dialog).getByRole("button", { name: "Send invitation" }),
      );
      expect(await within(dialog).findByText(title)).toBeInTheDocument();
      expect(screen.queryByText(/SERVER-MESSAGE/)).toBeNull();
      expect(toasts.success).not.toHaveBeenCalled();
      expect(state.refresh).not.toHaveBeenCalled();
    },
  );

  it("maps API field errors to the form", async () => {
    const api = installFetch();
    api.on(
      "POST /members/invitations",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "campus_ids", code: "unknown" }],
      }),
    );
    const { user, dialog } = await openInvite(api);
    await user.type(
      within(dialog).getByRole("textbox", { name: /Email/ }),
      "deck.cadet@coastal-maritime.example",
    );
    await user.type(
      within(dialog).getByRole("textbox", { name: /Full name/ }),
      "Kiran Shetty",
    );
    await user.click(
      within(dialog).getByRole("radio", { name: /Selected campuses/ }),
    );
    await user.click(
      within(dialog).getByRole("checkbox", { name: "Kochi Campus (KOC)" }),
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Send invitation" }),
    );
    expect(
      await within(dialog).findByText("Choose campuses of your institute."),
    ).toBeInTheDocument();
  });

  it("explains when roles and campuses can't be loaded, and retries", async () => {
    const api = installFetch();
    api.on(
      "GET /roles",
      apiError(500, "INTERNAL_ERROR"),
      jsonResponse(200, { data: ROLES, meta: {} }),
    );
    api.on(
      "GET /campuses",
      jsonResponse(200, { data: CAMPUS_LIST, meta: {} }),
      jsonResponse(200, { data: CAMPUS_LIST, meta: {} }),
    );
    state.reads = [["/members", ok([RAHUL], 1)]];
    const user = userEvent.setup();
    await show(list());
    await user.click(screen.getByRole("button", { name: "Invite member" }));
    const dialog = await screen.findByRole("dialog", { name: "Invite member" });
    expect(
      await within(dialog).findByText("Roles and campuses couldn't be loaded"),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole("button", { name: "Send invitation" }),
    ).toBeDisabled();
    await user.click(within(dialog).getByRole("button", { name: "Try again" }));
    expect(
      await within(dialog).findByRole("checkbox", { name: "Counsellor" }),
    ).toBeInTheDocument();
  });
});

// --- ADMIN-06 -------------------------------------------------------------------

describe("ADMIN-06 User detail", () => {
  it("needs member.read; another institute's member or a malformed ID is not found", async () => {
    state.session = readySession({ permissions: ["lead.read"] });
    await show(detail());
    expect(
      screen.getByRole("heading", {
        name: "You don't have access to this page",
      }),
    ).toBeInTheDocument();
    state.session = owner();
    state.reads = [
      [`/members/${MEMBER_IDS.priya}`, { kind: "not-found" }],
      ["/roles", ok(ROLES)],
      ["/campuses", ok(CAMPUS_LIST)],
    ];
    await expect(detail(MEMBER_IDS.priya)).rejects.toThrow("NEXT_NOT_FOUND");
    await expect(detail("../../platform")).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("shows the error state when the member can't be loaded", async () => {
    state.reads = [
      [
        `/members/${MEMBER_IDS.rahul}`,
        { kind: "error", reference: "req-4410" },
      ],
      ["/roles", ok(ROLES)],
      ["/campuses", ok(CAMPUS_LIST)],
    ];
    await show(detail());
    expect(
      screen.getByRole("heading", { name: "This member couldn't be loaded" }),
    ).toBeInTheDocument();
  });

  it.each(["light", "dark"] as const)(
    "shows identity, status, roles and campus access, counting campuses outside your access (%s)",
    async (theme) => {
      detailReads(
        member({ campus_ids: [CAMPUSES.kochi.id, MEMBER_IDS.hiddenCampus] }),
      );
      const { container } = await show(detail(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "Rahul Menon" }),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Can sign in to your institute."),
      ).toBeInTheDocument();
      const roles = screen
        .getByRole("heading", { level: 2, name: "Roles" })
        .closest("section") as HTMLElement;
      expect(within(roles).getByText("Counsellor")).toBeInTheDocument();
      expect(screen.getByText("Kochi Campus (KOC)")).toBeInTheDocument();
      expect(
        screen.getByText("And 1 campus outside your access"),
      ).toBeInTheDocument();
      await expectNoA11yViolations(container);
    },
  );

  it.each([
    ["ACTIVE", ["Suspend", "Remove from institute"]],
    ["INVITED", ["Resend invitation", "Remove from institute"]],
    ["SUSPENDED", ["Reinstate", "Remove from institute"]],
    ["REVOKED", ["Re-invite"]],
  ] as const)(
    "offers the status actions the API accepts for %s",
    async (status, expected) => {
      detailReads(member({ status }));
      await show(detail());
      const all = [
        "Resend invitation",
        "Re-invite",
        "Reinstate",
        "Suspend",
        "Remove from institute",
      ];
      for (const name of all) {
        const button = screen.queryByRole("button", { name });
        if ((expected as readonly string[]).includes(name)) {
          expect(button).toBeInTheDocument();
        } else expect(button).toBeNull();
      }
    },
  );

  it("offers nothing that needs a permission the session lacks", async () => {
    state.session = owner({ permissions: ["member.read"] });
    detailReads();
    await show(detail());
    for (const name of [
      "Suspend",
      "Remove from institute",
      "Change access",
      "Add role",
    ]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
    expect(
      screen.queryByRole("button", { name: /Remove the Counsellor role/ }),
    ).toBeNull();
  });

  it("protects your own membership in the UI: no status, campus or role-removal actions", async () => {
    detailReads(selfMember());
    await show(detail(MEMBER_IDS.self));
    expect(screen.getByText("This is your own membership")).toBeInTheDocument();
    for (const name of ["Suspend", "Remove from institute", "Change access"]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
    expect(
      screen.queryByRole("button", { name: /Remove the Institute owner role/ }),
    ).toBeNull();
    expect(
      screen.getByText(/You can't remove your own roles/),
    ).toBeInTheDocument();
  });

  it("suspends with the member's version, after asking", async () => {
    const api = installFetch();
    api.on(
      `POST /members/${MEMBER_IDS.rahul}/suspend`,
      jsonResponse(200, { data: member({ status: "SUSPENDED" }), meta: {} }),
    );
    detailReads();
    const user = userEvent.setup();
    await show(detail());
    await user.click(screen.getByRole("button", { name: "Suspend" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(
      within(dialog).getByRole("button", { name: "Suspend member" }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(
      api.callsTo(`POST /members/${MEMBER_IDS.rahul}/suspend`)[0]!.body,
    ).toEqual({ version: 3 });
    expect(toasts.success).toHaveBeenCalledWith("Rahul Menon was suspended.");
  });

  it("a 409 on removal names the last-owner rule and shows no success", async () => {
    const api = installFetch();
    api.on(
      `POST /members/${MEMBER_IDS.rahul}/revoke`,
      apiError(409, "CONFLICT"),
    );
    detailReads();
    const user = userEvent.setup();
    await show(detail());
    await user.click(
      screen.getByRole("button", { name: "Remove from institute" }),
    );
    const dialog = await screen.findByRole("alertdialog");
    await user.click(
      within(dialog).getByRole("button", { name: "Remove member" }),
    );
    await waitFor(() => expect(toasts.warning).toHaveBeenCalled());
    expect(toasts.warning.mock.calls[0]![0]).toMatch(/last active owner/);
    expect(toasts.success).not.toHaveBeenCalled();
    expect(state.refresh).toHaveBeenCalled();
  });

  it("a 403 on an action explains it without a success message", async () => {
    const api = installFetch();
    api.on(
      `POST /members/${MEMBER_IDS.rahul}/suspend`,
      apiError(403, "PERMISSION_DENIED"),
    );
    // The session re-read that follows a 403 (T01-05 §11).
    api.on("GET /session", jsonResponse(200, { data: owner(), meta: {} }));
    detailReads();
    const user = userEvent.setup();
    await show(detail());
    await user.click(screen.getByRole("button", { name: "Suspend" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(
      within(dialog).getByRole("button", { name: "Suspend member" }),
    );
    await waitFor(() =>
      expect(toasts.error).toHaveBeenCalledWith("You can't make this change", {
        description: expect.stringMatching(/your own membership/) as string,
      }),
    );
    expect(toasts.success).not.toHaveBeenCalled();
  });

  it("resends an invitation without a body and re-invites a removed member with the version", async () => {
    const api = installFetch();
    api.on(`POST /members/${MEMBER_IDS.priya}/invitation/resend`, noContent());
    detailReads(PRIYA);
    const user = userEvent.setup();
    const view = await show(detail(MEMBER_IDS.priya));
    await user.click(screen.getByRole("button", { name: "Resend invitation" }));
    await user.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Resend invitation",
      }),
    );
    await waitFor(() => expect(toasts.success).toHaveBeenCalled());
    expect(
      api.callsTo(`POST /members/${MEMBER_IDS.priya}/invitation/resend`)[0]!
        .body,
    ).toBeUndefined();
    view.unmount();

    api.on(
      `POST /members/${MEMBER_IDS.rahul}/reinvite`,
      jsonResponse(200, { data: member({ status: "INVITED" }), meta: {} }),
    );
    detailReads(member({ status: "REVOKED", version: 6 }));
    await show(detail());
    await user.click(screen.getByRole("button", { name: "Re-invite" }));
    await user.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Re-invite",
      }),
    );
    await waitFor(() =>
      expect(
        api.callsTo(`POST /members/${MEMBER_IDS.rahul}/reinvite`),
      ).toHaveLength(1),
    );
    expect(
      api.callsTo(`POST /members/${MEMBER_IDS.rahul}/reinvite`)[0]!.body,
    ).toEqual({ version: 6 });
  });

  it("adds a grantable role it doesn't hold yet; an ungrantable one isn't offered", async () => {
    const api = installFetch();
    api.on(
      `POST /members/${MEMBER_IDS.rahul}/roles`,
      jsonResponse(200, { data: member(), meta: {} }),
    );
    // All campuses: the Institute owner role is only offered with them (ADR-0023).
    detailReads(member({ campus_scope: "ALL", campus_ids: [] }));
    const user = userEvent.setup();
    await show(detail());
    await user.click(screen.getByRole("button", { name: /Add a role/ }));
    expect(
      await screen.findByRole("option", { name: "Institute owner" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Counsellor" })).toBeNull();
    expect(
      screen.queryByRole("option", { name: "Finance manager" }),
    ).toBeNull();
    await user.click(screen.getByRole("option", { name: "Institute owner" }));
    await user.click(screen.getByRole("button", { name: "Add role" }));
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(
      api.callsTo(`POST /members/${MEMBER_IDS.rahul}/roles`)[0]!.body,
    ).toEqual({ role_id: MEMBER_IDS.ownerRole });
  });

  it("removes a role after asking; a 409 names the last-owner rule", async () => {
    const api = installFetch();
    api.on(
      `DELETE /members/${MEMBER_IDS.rahul}/roles/${MEMBER_IDS.counsellorRole}`,
      apiError(409, "CONFLICT"),
    );
    detailReads();
    const user = userEvent.setup();
    await show(detail());
    await user.click(
      screen.getByRole("button", { name: "Remove the Counsellor role" }),
    );
    await user.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Remove role",
      }),
    );
    await waitFor(() => expect(toasts.warning).toHaveBeenCalled());
    expect(toasts.warning.mock.calls[0]![0]).toMatch(
      /at least one active owner/,
    );
    expect(toasts.success).not.toHaveBeenCalled();
  });

  it("changes campus access with the version; a field error stays in the dialog", async () => {
    const api = installFetch();
    api.on(
      `PUT /members/${MEMBER_IDS.rahul}/campus-scope`,
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "campus_ids", code: "unknown" }],
      }),
      jsonResponse(200, { data: member(), meta: {} }),
    );
    detailReads();
    const user = userEvent.setup();
    const { container } = await show(detail());
    await user.click(screen.getByRole("button", { name: "Change access" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Campus access for Rahul Menon",
    });
    await user.click(
      within(dialog).getByRole("checkbox", {
        name: "Visakhapatnam Campus (VTZ)",
      }),
    );
    await expectNoA11yViolations(container);
    await user.click(
      within(dialog).getByRole("button", { name: "Save access" }),
    );
    expect(
      await within(dialog).findByText("Choose campuses of your institute."),
    ).toBeInTheDocument();
    expect(toasts.success).not.toHaveBeenCalled();

    await user.click(
      within(dialog).getByRole("button", { name: "Save access" }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    const calls = api.callsTo(`PUT /members/${MEMBER_IDS.rahul}/campus-scope`);
    expect(calls[1]!.body).toEqual({
      campus_scope: "SELECTED",
      campus_ids: [CAMPUSES.kochi.id, CAMPUSES.vizag.id],
      version: 3,
    });
  });

  it("a stale version on campus access warns and shows the latest data", async () => {
    const api = installFetch();
    api.on(
      `PUT /members/${MEMBER_IDS.rahul}/campus-scope`,
      apiError(409, "CONFLICT"),
    );
    detailReads();
    const user = userEvent.setup();
    await show(detail());
    await user.click(screen.getByRole("button", { name: "Change access" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Campus access for Rahul Menon",
    });
    await user.click(
      within(dialog).getByRole("radio", { name: /All campuses/ }),
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Save access" }),
    );
    await waitFor(() => expect(toasts.warning).toHaveBeenCalled());
    expect(toasts.warning.mock.calls[0]![0]).toMatch(/changed by someone else/);
    expect(toasts.success).not.toHaveBeenCalled();
    expect(state.refresh).toHaveBeenCalled();
    expect(
      api.callsTo(`PUT /members/${MEMBER_IDS.rahul}/campus-scope`)[0]!.body,
    ).toEqual({ campus_scope: "ALL", campus_ids: [], version: 3 });
  });
});

// --- ADR-0023: owner campus scope and safe re-invitation ---------------------------

describe("Owner campus access and re-invitation (ADR-0023)", () => {
  const OWNER_ROLE = {
    id: MEMBER_IDS.ownerRole,
    name: "Institute owner",
    is_system: true,
    is_owner: true,
  };
  const OWNER_MEMBER = member({
    campus_scope: "ALL",
    campus_ids: [],
    roles: [OWNER_ROLE],
    is_owner: true,
  });
  const OWNER_SCOPE_ERROR =
    "An Institute owner needs access to all campuses. Choose All campuses.";
  const OWNER_ROLE_NEEDS_ALL =
    "Institute owner can only be given to a member with access to all campuses. Change their campus access first.";

  async function openCampusAccess(target: typeof RAHUL) {
    detailReads(target);
    const user = userEvent.setup();
    await show(detail());
    await user.click(screen.getByRole("button", { name: "Change access" }));
    const dialog = await screen.findByRole("dialog", {
      name: `Campus access for ${target.user.display_name}`,
    });
    return { user, dialog };
  }

  it("keeps an owner on all campuses: Selected campuses is disabled and says why", async () => {
    const api = installFetch();
    const { user, dialog } = await openCampusAccess(OWNER_MEMBER);
    expect(
      within(dialog).getByRole("radio", { name: /Selected campuses/ }),
    ).toBeDisabled();
    expect(
      within(dialog).getByText(
        /Institute owners always have access to all campuses/,
      ),
    ).toBeInTheDocument();
    await user.click(
      within(dialog).getByRole("radio", { name: /Selected campuses/ }),
    );
    expect(
      within(dialog).getByRole("radio", { name: /All campuses/ }),
    ).toBeChecked();
    expect(api.calls).toHaveLength(0);
  });

  it("shows the API's owner-scope refusal at the campus access field", async () => {
    const api = installFetch();
    api.on(
      `PUT /members/${MEMBER_IDS.rahul}/campus-scope`,
      apiError(422, "VALIDATION_ERROR", {
        details: [
          { field: "campus_scope", code: "owner_requires_all_campuses" },
        ],
      }),
    );
    const { user, dialog } = await openCampusAccess(RAHUL);
    await user.click(
      within(dialog).getByRole("checkbox", {
        name: "Visakhapatnam Campus (VTZ)",
      }),
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Save access" }),
    );
    expect(
      await within(dialog).findByText(OWNER_SCOPE_ERROR),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole("radiogroup", { name: "Campus access" }),
    ).toHaveAttribute("aria-invalid", "true");
    expect(toasts.success).not.toHaveBeenCalled();
    expect(screen.queryByText(/SERVER-/)).toBeNull();
  });

  it("an owner invitation needs all campuses before anything is sent", async () => {
    const api = installFetch();
    api.on("GET /roles", jsonResponse(200, { data: ROLES, meta: {} }));
    api.on("GET /campuses", jsonResponse(200, { data: CAMPUS_LIST, meta: {} }));
    api.on(
      "POST /members/invitations",
      jsonResponse(201, {
        data: { member: OWNER_MEMBER, account: "new" },
        meta: {},
      }),
    );
    state.reads = [["/members", ok([RAHUL], 1)]];
    const user = userEvent.setup();
    await show(list());
    await user.click(screen.getByRole("button", { name: "Invite member" }));
    const dialog = await screen.findByRole("dialog", { name: "Invite member" });
    await user.type(
      within(dialog).getByRole("textbox", { name: /Email/ }),
      "capt.nair@coastal-maritime.example",
    );
    await user.type(
      within(dialog).getByRole("textbox", { name: /Full name/ }),
      "Capt. Arjun Nair",
    );
    await user.click(
      await within(dialog).findByRole("checkbox", { name: "Institute owner" }),
    );
    expect(
      within(dialog).getByText(
        /Institute owners always have access to all campuses/,
      ),
    ).toBeInTheDocument();
    await user.click(
      within(dialog).getByRole("radio", { name: /Selected campuses/ }),
    );
    await user.click(
      within(dialog).getByRole("checkbox", { name: "Kochi Campus (KOC)" }),
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Send invitation" }),
    );
    expect(within(dialog).getByText(OWNER_SCOPE_ERROR)).toBeInTheDocument();
    expect(api.callsTo("POST /members/invitations")).toHaveLength(0);

    // The form never switches the access by itself; choosing All campuses sends it.
    await user.click(
      within(dialog).getByRole("radio", { name: /All campuses/ }),
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Send invitation" }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(api.callsTo("POST /members/invitations")[0]!.body).toMatchObject({
      role_ids: [MEMBER_IDS.ownerRole],
      campus_scope: "ALL",
      campus_ids: [],
    });
  });

  it("doesn't offer Institute owner to a campus-limited member, and says why", async () => {
    // Rahul is limited to Kochi; Institute owner is the only role this owner
    // could still give him, so nothing is offered and the reason is shown.
    detailReads(RAHUL);
    await show(detail());
    expect(screen.getByText(OWNER_ROLE_NEEDS_ALL)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Add a role/ })).toBeNull();
    expect(screen.queryByText(/Every role you can give/)).toBeNull();
  });

  it("still offers other roles to a campus-limited member", async () => {
    detailReads(
      member({
        roles: [],
      }),
    );
    const user = userEvent.setup();
    await show(detail());
    await user.click(screen.getByRole("button", { name: /Add a role/ }));
    expect(
      await screen.findByRole("option", { name: "Counsellor" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "Institute owner" }),
    ).toBeNull();
    expect(screen.getByText(OWNER_ROLE_NEEDS_ALL)).toBeInTheDocument();
  });

  it("explains the API's owner-scope refusal when a role is added", async () => {
    const api = installFetch();
    api.on(
      `POST /members/${MEMBER_IDS.rahul}/roles`,
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "role_id", code: "owner_requires_all_campuses" }],
      }),
    );
    detailReads(member({ campus_scope: "ALL", campus_ids: [] }));
    const user = userEvent.setup();
    await show(detail());
    await user.click(screen.getByRole("button", { name: /Add a role/ }));
    await user.click(
      await screen.findByRole("option", { name: "Institute owner" }),
    );
    await user.click(screen.getByRole("button", { name: "Add role" }));
    expect(
      await screen.findByText("The role wasn't added"),
    ).toBeInTheDocument();
    expect(screen.getByText(OWNER_ROLE_NEEDS_ALL)).toBeInTheDocument();
    expect(toasts.success).not.toHaveBeenCalled();
  });

  it("says re-invitation removes previous roles, and a re-invited member shows none", async () => {
    const api = installFetch();
    api.on(
      `POST /members/${MEMBER_IDS.rahul}/reinvite`,
      jsonResponse(200, {
        data: member({ status: "INVITED", roles: [], version: 7 }),
        meta: {},
      }),
    );
    detailReads(member({ status: "REVOKED", version: 6 }));
    const user = userEvent.setup();
    const view = await show(detail());
    await user.click(screen.getByRole("button", { name: "Re-invite" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(
      within(dialog).getByText(/Their previous roles are removed/),
    ).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Re-invite" }));
    await waitFor(() => expect(toasts.success).toHaveBeenCalled());
    expect(
      api.callsTo(`POST /members/${MEMBER_IDS.rahul}/reinvite`)[0]!.body,
    ).toEqual({ version: 6 });
    view.unmount();

    // The refreshed page: no roles, and roles can be assigned again.
    detailReads(member({ status: "INVITED", roles: [], version: 7 }));
    await show(detail());
    expect(screen.getByText(/No roles yet/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Add a role/ }),
    ).toBeInTheDocument();
  });
});
