import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectHeadingOutline } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import type { ReadResult } from "@/lib/api/server-read";
import type { SessionWire } from "@/lib/api/types";
import {
  activity,
  ADMISSIONS_COUNSELLOR,
  applicationItem,
  COUNSELLOR,
  course,
  followUp,
  IDS,
  lead,
  MANAGER,
  ok,
} from "@/test/admissions-fixtures";
import { apiError, installFetch, jsonResponse } from "@/test/fetch-mock";
import { readySession } from "@/test/session-fixtures";

import { TenantFrame } from "../../tenant-frame";

import EditLeadPage from "./[leadId]/edit/page";
import LeadDetailPage, { metadata } from "./[leadId]/page";
import NewLeadPage from "./new/page";

import type { ReactElement } from "react";

vi.setConfig({ testTimeout: 30_000 });

// Lead create / edit with the duplicate warning, and GROW-09 Lead detail with
// status, assignment, follow-ups and notes (Phase 02-1; blueprint §21, §24).

const state = vi.hoisted(() => ({
  session: null as SessionWire | null,
  reads: [] as [string, ReadResult<unknown>][],
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/app/admissions/leads",
  useSearchParams: () => new URLSearchParams(),
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
    const found = state.reads.find(([pattern]) => p.startsWith(pattern));
    return found
      ? Promise.resolve(found[1])
      : Promise.reject(new Error(`unexpected read ${p}`));
  },
}));

beforeEach(() => {
  state.session = readySession({ permissions: COUNSELLOR });
  state.reads = [["/courses", ok([course()], 1)]];
  state.push.mockReset();
  state.replace.mockReset();
  state.refresh.mockReset();
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

const detail = () =>
  LeadDetailPage({ params: Promise.resolve({ leadId: IDS.arjun }) });

function detailReads(overrides: Parameters<typeof lead>[0] = {}) {
  state.reads.unshift(
    [`/leads/${IDS.arjun}/follow-ups`, ok({ items: [followUp()] })],
    [
      `/leads/${IDS.arjun}/activity`,
      ok(
        [
          activity({
            id: "n1",
            kind: "NOTE",
            body: "Father is a Chief Engineer; call after 6 pm.",
            details: {},
          }),
          activity(),
        ],
        2,
      ),
    ],
    [`/leads/${IDS.arjun}`, ok(lead(overrides))],
  );
}

// --- Create, validate, warn ------------------------------------------------------------

describe("new lead", () => {
  it("needs lead.create", async () => {
    state.session = readySession({ permissions: ["lead.read"] });
    await show(NewLeadPage());
    expect(
      screen.getByText("You don't have access to this page"),
    ).toBeInTheDocument();
  });

  it("requires a name and a mobile or an email, and focuses the first problem", async () => {
    const user = userEvent.setup();
    installFetch();
    const { container } = await show(NewLeadPage());
    await user.click(screen.getByRole("button", { name: "Create lead" }));
    expect(
      await screen.findByText("Enter the enquirer's name."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Enter a mobile number or an email."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Choose where the enquiry came from."),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: /Full name/ })).toHaveFocus(),
    );
    expectHeadingOutline(container);
    await expectNoA11yViolations(container);
  });

  it("counsellors choose only Me or Unassigned as owner; campus is theirs or institute-wide", async () => {
    const user = userEvent.setup();
    installFetch();
    await show(NewLeadPage());
    await user.click(screen.getByRole("button", { name: /Owner/ }));
    expect(
      (await screen.findAllByRole("option")).map((o) => o.textContent),
    ).toEqual(["Me", "Unassigned"]);
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: /Campus/ }));
    expect(
      (await screen.findAllByRole("option")).map((o) => o.textContent),
    ).toEqual(["Institute-wide (all campuses)", "Kochi Campus"]);
  });

  it("warns about a possible duplicate without blocking, then asks once before creating", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      "POST /leads/duplicate-check",
      jsonResponse(200, {
        data: {
          candidates: [
            {
              id: IDS.meera,
              full_name: "Meera Iyer",
              status: "CONTACTED",
              course_name: "GP Rating",
              campus_name: null,
              owner_name: "Ravi Menon",
              created_at: "2026-10-01T05:00:00Z",
              matched_on: ["mobile"],
            },
          ],
        },
      }),
    );
    api.on("POST /leads", jsonResponse(201, { data: lead() }));
    const { container } = await show(NewLeadPage());
    await user.type(
      screen.getByRole("textbox", { name: /Full name/ }),
      "Arjun Nair",
    );
    await user.type(
      screen.getByRole("textbox", { name: /Mobile/ }),
      "+91 90000 10001",
    );
    await user.tab();
    const warning = await screen.findByText("Possible duplicate lead");
    const alert = warning.closest('[role="status"]') as HTMLElement;
    const open = within(alert).getByRole("link", {
      name: /Open lead: Meera Iyer/,
    });
    expect(open).toHaveAttribute("href", `/app/admissions/leads/${IDS.meera}`);
    expect(open).toHaveAttribute("target", "_blank");
    expect(within(alert).getByText("Matched on mobile")).toBeInTheDocument();
    await expectNoA11yViolations(container);

    await user.click(screen.getByRole("button", { name: /Source/ }));
    await user.click(await screen.findByRole("option", { name: "Walk-in" }));
    // Submit stays enabled; it asks once.
    await user.click(screen.getByRole("button", { name: "Create lead" }));
    const confirm = await screen.findByRole("alertdialog", {
      name: "Create anyway?",
    });
    await user.click(
      within(confirm).getByRole("button", { name: "Create lead" }),
    );
    await waitFor(() =>
      expect(state.push).toHaveBeenCalledWith(
        `/app/admissions/leads/${IDS.arjun}`,
      ),
    );
    expect(api.callsTo("POST /leads")[0]!.body).toEqual({
      full_name: "Arjun Nair",
      mobile: "+91 90000 10001",
      email: null,
      source: "WALK_IN",
      interested_course_id: null,
      date_of_birth: null,
      city: null,
      highest_qualification: null,
      campus_id: null,
      owner: "me",
    });
    // Contact details travel in the POST body, never in a URL.
    for (const call of api.calls) {
      expect(call.path).not.toContain("90000");
    }
  });

  it("a failed duplicate check shows nothing and creation proceeds", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on("POST /leads/duplicate-check", apiError(500, "INTERNAL_ERROR"));
    api.on("POST /leads", jsonResponse(201, { data: lead() }));
    await show(NewLeadPage());
    await user.type(
      screen.getByRole("textbox", { name: /Full name/ }),
      "Arjun Nair",
    );
    await user.type(
      screen.getByRole("textbox", { name: /Email/ }),
      "arjun@example.com",
    );
    await user.click(screen.getByRole("button", { name: /Source/ }));
    await user.click(await screen.findByRole("option", { name: "Website" }));
    await user.click(screen.getByRole("button", { name: "Create lead" }));
    await waitFor(() => expect(state.push).toHaveBeenCalled());
    expect(screen.queryByText("Possible duplicate lead")).toBeNull();
    expect(
      screen.queryByRole("alertdialog", { name: "Create anyway?" }),
    ).toBeNull();
  });

  it("maps the API's field codes to fixed copy", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      "POST /leads/duplicate-check",
      jsonResponse(200, { data: { candidates: [] } }),
    );
    api.on(
      "POST /leads",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "interested_course_id", code: "course_not_active" }],
      }),
    );
    await show(NewLeadPage());
    await user.type(
      screen.getByRole("textbox", { name: /Full name/ }),
      "Arjun Nair",
    );
    await user.type(
      screen.getByRole("textbox", { name: /Mobile/ }),
      "9000010001",
    );
    await user.click(screen.getByRole("button", { name: /Source/ }));
    await user.click(await screen.findByRole("option", { name: "Phone call" }));
    await user.click(screen.getByRole("button", { name: "Create lead" }));
    expect(
      await screen.findByText(
        "This course is no longer active. Choose an active course.",
      ),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("SERVER-");
  });
});

// --- Edit -------------------------------------------------------------------------------

describe("edit lead", () => {
  it("keeps an archived course, sends the version and has no campus or owner fields", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      "POST /leads/duplicate-check",
      jsonResponse(200, { data: { candidates: [] } }),
    );
    api.on(`PATCH /leads/${IDS.arjun}`, apiError(409, "CONFLICT"));
    state.reads.unshift([
      `/leads/${IDS.arjun}`,
      ok(
        lead({
          interested_course: {
            id: IDS.ccmc,
            code: "CCMC",
            name: "Crowd and Crisis Management",
            status: "ARCHIVED",
          },
        }),
      ),
    ]);
    await show(
      EditLeadPage({ params: Promise.resolve({ leadId: IDS.arjun }) }),
    );
    expect(screen.queryByRole("button", { name: /Campus/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Owner/ })).toBeNull();
    expect(
      screen.getByRole("combobox", { name: /Interested course/ }),
    ).toHaveValue("CCMC · Crowd and Crisis Management (no longer active)");
    await user.clear(screen.getByRole("textbox", { name: /City/ }));
    await user.type(screen.getByRole("textbox", { name: /City/ }), "Alappuzha");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(
      await screen.findByText("This was changed by someone else"),
    ).toBeInTheDocument();
    expect(api.callsTo(`PATCH /leads/${IDS.arjun}`)[0]!.body).toMatchObject({
      city: "Alappuzha",
      interested_course_id: IDS.ccmc,
      version: 3,
    });
  });
});

// --- Detail -----------------------------------------------------------------------------

describe("GROW-09 lead detail", () => {
  it.each(["light", "dark"] as const)(
    "shows the enquiry, pipeline, follow-ups and history (%s)",
    async (theme) => {
      detailReads();
      const { container } = await show(detail(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "Arjun Nair" }),
      ).toBeInTheDocument();
      const aside = screen.getByRole("complementary", {
        name: "Lead pipeline and follow-ups",
      });
      expect(screen.getByText("GPR · GP Rating")).toBeInTheDocument();
      expect(within(aside).getByText("Kochi Campus")).toBeInTheDocument();
      expect(within(aside).getByText("Ravi Menon")).toBeInTheDocument();
      const open = screen.getByRole("list", { name: "Open follow-ups" });
      expect(within(open).getByText("Overdue")).toBeInTheDocument();
      expect(
        screen.getByText("Father is a Chief Engineer; call after 6 pm."),
      ).toBeInTheDocument();
      // Counsellor: edit and status, no assignment.
      expect(
        screen.getByRole("button", { name: "Change status" }),
      ).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Assign" })).toBeNull();
      // The name is never in the page title (metadata is fixed).
      expect(metadata.title).toBe("Lead · Tenant Application · MTI 360");
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("readers without lead.update get no actions", async () => {
    state.session = readySession({ permissions: ["lead.read"] });
    detailReads();
    await show(detail());
    for (const name of ["Change status", "Schedule", "Add note", "Mark done"]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
    expect(screen.queryByRole("link", { name: "Edit" })).toBeNull();
  });

  it("Phase 02-2: starts an application and lists the lead's applications", async () => {
    state.session = readySession({ permissions: ADMISSIONS_COUNSELLOR });
    detailReads({ status: "INTERESTED" });
    state.reads.unshift([
      "/applications?lead=",
      ok([applicationItem({ status: "DRAFT" })], 1),
    ]);
    await show(detail());
    expect(
      screen.getByRole("link", { name: "Start application" }),
    ).toHaveAttribute(
      "href",
      `/app/admissions/applications/new?lead=${IDS.arjun}`,
    );
    expect(
      screen.getByRole("link", { name: "APP-2026-00012 · GPR" }),
    ).toHaveAttribute(
      "href",
      `/app/admissions/applications/${IDS.application}`,
    );
  });

  it("Phase 02-2: a closed lead, or a member without application.create, cannot start one", async () => {
    state.session = readySession({ permissions: ADMISSIONS_COUNSELLOR });
    detailReads({ status: "LOST", status_reason: "Joined another institute" });
    state.reads.unshift(["/applications?lead=", ok([], 0)]);
    const { unmount } = await show(detail());
    expect(
      screen.queryByRole("link", { name: "Start application" }),
    ).toBeNull();
    expect(screen.getByText("No applications yet")).toBeInTheDocument();
    unmount();
    state.session = readySession({ permissions: COUNSELLOR });
    await show(detail());
    expect(
      screen.queryByRole("link", { name: "Start application" }),
    ).toBeNull();
  });

  it("another institute's, another campus's or a malformed lead is not found", async () => {
    state.reads.unshift(
      [`/leads/${IDS.arjun}/follow-ups`, { kind: "not-found" }],
      [`/leads/${IDS.arjun}/activity`, { kind: "not-found" }],
      [`/leads/${IDS.arjun}`, { kind: "not-found" }],
    );
    await expect(detail()).rejects.toThrow("NEXT_NOT_FOUND");
    await expect(
      LeadDetailPage({ params: Promise.resolve({ leadId: "1 OR 1=1" }) }),
    ).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("closing as lost needs a reason; the server's answer refreshes the page", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `POST /leads/${IDS.arjun}/transition`,
      jsonResponse(200, { data: lead() }),
    );
    detailReads();
    await show(detail());
    await user.click(screen.getByRole("button", { name: "Change status" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(
      within(dialog).getByRole("button", { name: /New status/ }),
    );
    await user.click(await screen.findByRole("option", { name: "Lost" }));
    await user.click(
      within(dialog).getByRole("button", { name: "Save status" }),
    );
    expect(
      await within(dialog).findByText("Enter a reason."),
    ).toBeInTheDocument();
    await user.type(
      within(dialog).getByRole("textbox", { name: /Reason/ }),
      "Joined another institute",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Save status" }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(api.callsTo(`POST /leads/${IDS.arjun}/transition`)[0]!.body).toEqual(
      {
        to_status: "LOST",
        reason: "Joined another institute",
        duplicate_of_lead_id: null,
        version: 3,
      },
    );
  });

  it("managers assign owner and campus from eligible members only", async () => {
    const user = userEvent.setup();
    state.session = readySession({
      permissions: MANAGER,
      all_campuses_allowed: true,
    });
    const api = installFetch();
    api.on(
      "GET /leads/assignees",
      jsonResponse(200, {
        data: {
          items: [{ membership_id: IDS.ravi, display_name: "Ravi Menon" }],
        },
      }),
      jsonResponse(200, { data: { items: [] } }),
    );
    api.on(
      `POST /leads/${IDS.arjun}/assign`,
      jsonResponse(200, { data: lead() }),
    );
    detailReads();
    await show(detail());
    await user.click(screen.getByRole("button", { name: "Assign" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Assign Arjun Nair",
    });
    await user.click(within(dialog).getByRole("button", { name: /Campus/ }));
    await user.click(
      await screen.findByRole("option", {
        name: "Institute-wide (all campuses)",
      }),
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Save assignment" }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(api.callsTo(`POST /leads/${IDS.arjun}/assign`)[0]!.body).toEqual({
      owner_membership_id: IDS.ravi,
      campus_id: null,
      version: 3,
    });
    expect(
      api.calls.filter((c) => c.path.startsWith("/leads/assignees")).length,
    ).toBeGreaterThan(0);
  });

  it("schedules a follow-up with a time-zone-aware time and completes one", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `POST /leads/${IDS.arjun}/follow-ups`,
      jsonResponse(201, { data: followUp() }),
    );
    api.on(
      `POST /lead-follow-ups/${IDS.followUp}/complete`,
      jsonResponse(200, { data: followUp({ status: "DONE" }) }),
    );
    detailReads();
    await show(detail());
    await user.click(screen.getByRole("button", { name: "Schedule" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Schedule a follow-up",
    });
    await user.click(within(dialog).getByRole("button", { name: "Schedule" }));
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    const body = api.callsTo(`POST /leads/${IDS.arjun}/follow-ups`)[0]!
      .body as {
      due_at: string;
      kind: string;
    };
    expect(body.kind).toBe("CALL");
    expect(body.due_at).toMatch(/Z$/);
    expect(body).not.toHaveProperty("assignee_membership_id");

    await user.click(screen.getByRole("button", { name: "Mark done" }));
    const done = await screen.findByRole("dialog", {
      name: "Mark follow-up done",
    });
    await user.type(
      within(done).getByRole("textbox", { name: /Outcome/ }),
      "Visited with parents",
    );
    await user.click(within(done).getByRole("button", { name: "Mark done" }));
    await waitFor(() =>
      expect(
        api.callsTo(`POST /lead-follow-ups/${IDS.followUp}/complete`),
      ).toHaveLength(1),
    );
    expect(
      api.callsTo(`POST /lead-follow-ups/${IDS.followUp}/complete`)[0]!.body,
    ).toEqual({
      outcome: "Visited with parents",
      version: 1,
    });
  });

  it("adds an append-only plain-text note", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `POST /leads/${IDS.arjun}/notes`,
      jsonResponse(201, { data: activity({ kind: "NOTE" }) }),
    );
    detailReads();
    await show(detail());
    await user.click(screen.getByRole("button", { name: "Add note" }));
    expect(await screen.findByText("Write a note.")).toBeInTheDocument();
    await user.type(
      screen.getByRole("textbox", { name: /Add a note/ }),
      "Interested in DNS too.",
    );
    await user.click(screen.getByRole("button", { name: "Add note" }));
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(api.callsTo(`POST /leads/${IDS.arjun}/notes`)[0]!.body).toEqual({
      body: "Interested in DNS too.",
    });
    expect(
      screen.queryByRole("button", { name: /Edit note|Delete note/ }),
    ).toBeNull();
  });
});

// --- Source rules -----------------------------------------------------------------------

describe("source rules", () => {
  const SRC = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../../../..",
  );
  const FILES = [
    "features/leads/LeadForm.tsx",
    "features/leads/LeadsWorkspace.tsx",
    "features/leads/LeadBoard.tsx",
    "features/leads/LeadTable.tsx",
    "features/leads/LeadStatusDialog.tsx",
    "features/leads/AssignLeadDialog.tsx",
    "features/leads/FollowUpsPanel.tsx",
    "features/leads/LeadActivity.tsx",
    "features/leads/DuplicateWarning.tsx",
    "features/courses/CourseForm.tsx",
    "features/courses/CourseList.tsx",
    "features/courses/CourseActions.tsx",
    "features/shared/StatusTransitionDialog.tsx",
    "features/activity/ActivityFeed.tsx",
    "app/app/admissions/leads/page.tsx",
    "app/app/admissions/leads/[leadId]/page.tsx",
    "app/app/academics/courses/page.tsx",
  ];

  it("no role-name gating, storage, logging or tenant IDs from the browser (raw HTML: the global guard)", () => {
    for (const file of FILES) {
      const source = readFileSync(path.join(SRC, file), "utf8");
      expect(source, file).not.toMatch(/roles\.(includes|some|find|indexOf)\(/);
      expect(source, file).not.toMatch(
        /localStorage|sessionStorage|indexedDB|document\.cookie/,
      );
      expect(source, file).not.toMatch(
        /console\.(log|info|warn|error|debug|trace)\(/,
      );
      expect(source, file).not.toMatch(/tenant_id/);
      expect(source, file).not.toMatch(/["'`]\/platform/);
    }
  });
});
