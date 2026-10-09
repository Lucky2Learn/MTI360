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
  ADMISSIONS_COUNSELLOR,
  ADMISSIONS_MANAGER,
  application,
  applicationActivity,
  applicationItem,
  candidate,
  course,
  documentWire,
  IDS,
  lead,
  ok,
} from "@/test/admissions-fixtures";
import { apiError, installFetch, jsonResponse } from "@/test/fetch-mock";
import { readySession } from "@/test/session-fixtures";

import { TenantFrame } from "../../tenant-frame";

import EditApplicationPage from "./[applicationId]/edit/page";
import ApplicationDetailPage from "./[applicationId]/page";
import NewApplicationPage from "./new/page";
import ApplicationsPage from "./page";

import type { ReactElement } from "react";

vi.setConfig({ testTimeout: 30_000 });

// ADM-05 Applications, ADM-07 New application and its wizard, ADM-06
// Application detail with ADM-08 review, ADM-09 documents and ADM-10
// admission (Phase 02-2; ADR-0021 §14): gates, permission-dependent actions,
// states, request bodies, error mapping and axe in Light and Dark.

const state = vi.hoisted(() => ({
  session: null as SessionWire | null,
  reads: [] as [string, ReadResult<unknown>][],
  paths: [] as string[],
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/app/admissions/applications",
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
    state.paths.push(p);
    const found = state.reads.find(([pattern]) => p.startsWith(pattern));
    return found
      ? Promise.resolve(found[1])
      : Promise.reject(new Error(`unexpected read ${p}`));
  },
}));

beforeEach(() => {
  state.session = readySession({ permissions: ADMISSIONS_COUNSELLOR });
  state.reads = [["/courses", ok([course()], 1)]];
  state.paths = [];
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

const APP = `/applications/${IDS.application}`;
const list = (search: Record<string, string> = {}) =>
  ApplicationsPage({ searchParams: Promise.resolve(search) });
const detail = () =>
  ApplicationDetailPage({
    params: Promise.resolve({ applicationId: IDS.application }),
  });
const edit = (step: string) =>
  EditApplicationPage({
    params: Promise.resolve({ applicationId: IDS.application }),
    searchParams: Promise.resolve({ step }),
  });

function detailReads(
  overrides: Parameters<typeof application>[0] = {},
  documents = [documentWire()],
) {
  state.reads.unshift(
    [`${APP}/documents`, ok({ items: documents })],
    [`${APP}/activity`, ok([applicationActivity()], 1)],
    [APP, ok(application(overrides))],
  );
}

// --- ADM-05 -----------------------------------------------------------------------------

describe("ADM-05 Applications", () => {
  it("needs a session, then application.read (AUTHZ-01 at the same URL)", async () => {
    state.session = null;
    await expect(list()).rejects.toThrow(
      "NEXT_REDIRECT /session-ended?next=/app/admissions/applications",
    );
    state.session = readySession({ permissions: ["lead.read"] });
    await show(list());
    expect(
      screen.getByText("You don't have access to this page"),
    ).toBeInTheDocument();
  });

  it.each(["light", "dark"] as const)(
    "lists applications with status and pending documents, and passes axe (%s)",
    async (theme) => {
      state.reads.unshift([
        "/applications",
        ok(
          [
            applicationItem(),
            applicationItem({
              id: "x2",
              number: "APP-2026-00013",
              full_name: "Meera Pillai",
              status: "APPROVED",
              documents_pending: 0,
            }),
          ],
          2,
        ),
      ]);
      const { container } = await show(list(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "Applications" }),
      ).toBeInTheDocument();
      const table = screen.getByRole("table", { name: "Applications" });
      expect(
        within(table).getByRole("link", { name: "Arjun Nair" }),
      ).toHaveAttribute(
        "href",
        `/app/admissions/applications/${IDS.application}`,
      );
      expect(within(table).getByText("Submitted")).toBeInTheDocument();
      expect(within(table).getByText("Approved")).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "New application" }),
      ).toHaveAttribute("href", "/app/admissions/applications/new");
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("forwards only known filters, and shows the empty and error states", async () => {
    state.reads.unshift(["/applications", ok([], 0)]);
    await show(
      list({
        status: "APPROVED",
        owner: "me",
        lead: "not-an-id",
        tenant_id: "x",
      }),
    );
    const read = state.paths.find((p) => p.startsWith("/applications?")) ?? "";
    const query = new URLSearchParams(read.split("?")[1]);
    expect(query.get("status")).toBe("APPROVED");
    expect(query.get("owner")).toBe("me");
    expect(query.has("lead")).toBe(false);
    expect(query.has("tenant_id")).toBe(false);
    expect(screen.getAllByText("No applications yet").length).toBeGreaterThan(
      0,
    );
  });

  it("reports a failed load with the support reference only", async () => {
    state.reads.unshift([
      "/applications",
      { kind: "error", reference: "req-7781" },
    ]);
    await show(list());
    expect(
      screen.getByText("Applications couldn't be loaded"),
    ).toBeInTheDocument();
    expect(screen.getByText(/req-7781/)).toBeInTheDocument();
  });

  it("readers without application.create get no New application action", async () => {
    state.session = readySession({ permissions: ["application.read"] });
    state.reads.unshift(["/applications", ok([], 0)]);
    await show(list());
    expect(
      screen.queryByRole("link", { name: "New application" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getAllByText("Applications of your campuses appear here.").length,
    ).toBeGreaterThan(0);
  });
});

// --- ADM-07 start -----------------------------------------------------------------------

describe("ADM-07 New application", () => {
  const start = (search: Record<string, string> = {}) =>
    NewApplicationPage({ searchParams: Promise.resolve(search) });

  it("needs application.create", async () => {
    state.session = readySession({ permissions: ["application.read"] });
    await show(start());
    expect(
      screen.getByText("You don't have access to this page"),
    ).toBeInTheDocument();
  });

  it("from a lead: course and campus are prefilled, and the draft continues in the wizard", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on("POST /applications", jsonResponse(201, { data: application() }));
    state.reads.unshift([`/leads/${IDS.arjun}`, ok(lead())]);
    await show(start({ lead: IDS.arjun }));
    expect(screen.getByText("From lead: Arjun Nair")).toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: /Full name/ }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start application" }));
    await waitFor(() =>
      expect(state.push).toHaveBeenCalledWith(
        `/app/admissions/applications/${IDS.application}/edit?step=personal`,
      ),
    );
    expect(api.callsTo("POST /applications")[0]!.body).toEqual({
      course_id: IDS.gpr,
      campus_id: "a3f1c2d4-5b6e-4f70-8a9b-0c1d2e3f4a11",
      lead_id: IDS.arjun,
    });
  });

  it("direct: needs a name and a contact, and maps the API's codes to fixed copy", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      "POST /applications",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "course_id", code: "application_exists" }],
      }),
    );
    await show(start());
    await user.click(screen.getByRole("button", { name: "Start application" }));
    expect(await screen.findByText("Choose the course.")).toBeInTheDocument();
    expect(screen.getByText("Enter the applicant's name.")).toBeInTheDocument();
    expect(
      screen.getByText("Enter a mobile number or an email."),
    ).toBeInTheDocument();
    expect(api.callsTo("POST /applications")).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: /Course/ }));
    await user.click(
      await screen.findByRole("option", { name: "GPR · GP Rating" }),
    );
    await user.type(
      screen.getByRole("textbox", { name: /Full name/ }),
      "Meera Pillai",
    );
    await user.type(
      screen.getByRole("textbox", { name: /Mobile/ }),
      "+91 90000 10044",
    );
    await user.click(screen.getByRole("button", { name: "Start application" }));
    expect(
      await screen.findByText(
        "This lead already has an open application for this course.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/SERVER-/)).not.toBeInTheDocument();
  });
});

// --- ADM-07 wizard ----------------------------------------------------------------------

describe("ADM-07 application wizard", () => {
  it("lists the steps, saves only changed fields with the version and moves on", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `PATCH ${APP}`,
      jsonResponse(200, { data: application({ version: 3 }) }),
    );
    state.reads.unshift([APP, ok(application())]);
    const { container } = await show(edit("contact"));
    const steps = screen.getByRole("navigation", { name: "Application steps" });
    expect(
      within(steps).getByRole("link", { name: /Contact/ }),
    ).toHaveAttribute("aria-current", "step");
    expect(within(steps).getByText(/Step 3 of 6: Contact/)).toBeInTheDocument();
    await user.type(
      screen.getByRole("textbox", { name: /PIN code/ }),
      "682001",
    );
    await user.click(screen.getByRole("button", { name: "Save and continue" }));
    await waitFor(() =>
      expect(state.push).toHaveBeenCalledWith(
        `/app/admissions/applications/${IDS.application}/edit?step=education`,
      ),
    );
    expect(api.callsTo(`PATCH ${APP}`)[0]!.body).toEqual({
      postal_code: "682001",
      version: 2,
    });
    await expectNoA11yViolations(container);
  });

  it("requires a name, maps invalid codes, and skips the request when nothing changed", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `PATCH ${APP}`,
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "indos_number", code: "invalid" }],
      }),
    );
    state.reads.unshift([APP, ok(application())]);
    await show(edit("personal"));
    await user.clear(screen.getByRole("textbox", { name: /Full name/ }));
    await user.click(screen.getByRole("button", { name: "Save and continue" }));
    expect(
      await screen.findByText("Enter the applicant's name."),
    ).toBeInTheDocument();
    await user.type(
      screen.getByRole("textbox", { name: /Full name/ }),
      "Arjun Nair",
    );
    await user.click(screen.getByRole("button", { name: "Save and continue" }));
    await waitFor(() => expect(state.push).toHaveBeenCalled());
    expect(api.callsTo(`PATCH ${APP}`)).toHaveLength(0);
  });

  it("records the staff-confirmed declaration", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(`PATCH ${APP}`, jsonResponse(200, { data: application() }));
    state.reads.unshift([APP, ok(application())]);
    await show(edit("declaration"));
    await user.click(
      screen.getByRole("checkbox", { name: /applicant has confirmed/ }),
    );
    await user.click(screen.getByRole("button", { name: "Save and continue" }));
    await waitFor(() => expect(api.callsTo(`PATCH ${APP}`)).toHaveLength(1));
    expect(api.callsTo(`PATCH ${APP}`)[0]!.body).toEqual({
      declaration_confirmed: true,
      version: 2,
    });
  });

  it("review: lists what is missing; a complete application is submitted once", async () => {
    const user = userEvent.setup();
    state.reads.unshift([APP, ok(application())]);
    const { unmount } = await show(edit("review"));
    expect(
      screen.getByText("Complete these before submitting"),
    ).toBeInTheDocument();
    expect(screen.getByText("The applicant's declaration")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Submit application" }),
    ).toBeDisabled();
    unmount();

    const api = installFetch();
    api.on(
      `POST ${APP}/submit`,
      jsonResponse(200, { data: application({ status: "SUBMITTED" }) }),
    );
    state.reads = [
      [
        APP,
        ok(
          application({
            missing_for_submit: [],
            declared_at: "2026-10-09T06:00:00Z",
          }),
        ),
      ],
    ];
    await show(edit("review"));
    await user.click(
      screen.getByRole("button", { name: "Submit application" }),
    );
    await waitFor(() =>
      expect(state.push).toHaveBeenCalledWith(
        `/app/admissions/applications/${IDS.application}`,
      ),
    );
    expect(api.callsTo(`POST ${APP}/submit`)[0]!.body).toEqual({ version: 2 });
  });

  it("a submitted application is not edited here", async () => {
    state.reads.unshift([
      APP,
      ok(application({ status: "SUBMITTED", editable: false })),
    ]);
    await show(edit("personal"));
    expect(
      screen.getByText("This application has been submitted"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save and continue" }),
    ).not.toBeInTheDocument();
  });
});

// --- ADM-06 detail ----------------------------------------------------------------------

describe("ADM-06 Application detail", () => {
  it.each(["light", "dark"] as const)(
    "counsellors continue the draft and upload documents, but never review or admit (%s)",
    async (theme) => {
      detailReads();
      const { container } = await show(detail(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "Arjun Nair" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "Continue application" }),
      ).toHaveAttribute(
        "href",
        `/app/admissions/applications/${IDS.application}/edit?step=personal`,
      );
      expect(
        screen.queryByRole("button", { name: "Review" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Approve admission" }),
      ).not.toBeInTheDocument();
      expect(
        screen.getByText("Before this application can be submitted"),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Upload document" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Verify" }),
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: /arjun-passport\.pdf/ }),
      ).toHaveAttribute("href", `/api/v1/documents/${IDS.passport}/download`);
      expect(screen.getByRole("link", { name: "Arjun Nair" })).toHaveAttribute(
        "href",
        `/app/admissions/leads/${IDS.arjun}`,
      );
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("needs application.read; another campus's application is not found", async () => {
    state.session = readySession({ permissions: ["lead.read"] });
    await show(detail());
    expect(
      screen.getByText("You don't have access to this page"),
    ).toBeInTheDocument();
    state.session = readySession({ permissions: ADMISSIONS_COUNSELLOR });
    state.reads.unshift([APP, { kind: "not-found" }]);
    await expect(detail()).rejects.toThrow("NEXT_NOT_FOUND");
    await expect(
      ApplicationDetailPage({
        params: Promise.resolve({ applicationId: "../x" }),
      }),
    ).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("without document.read the documents are neither read nor shown", async () => {
    state.session = readySession({ permissions: ["application.read"] });
    detailReads();
    await show(detail());
    expect(state.paths.some((p) => p.endsWith("/documents"))).toBe(false);
    expect(
      screen.queryByRole("heading", { name: "Documents" }),
    ).not.toBeInTheDocument();
  });

  it("reviewers decide with the server's options; reasons and unverified documents are explained", async () => {
    const user = userEvent.setup();
    state.session = readySession({ permissions: ADMISSIONS_MANAGER });
    const api = installFetch();
    api.on(
      `POST ${APP}/review`,
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "documents", code: "documents_not_verified" }],
      }),
      jsonResponse(200, { data: application({ status: "REJECTED" }) }),
    );
    detailReads({
      status: "SUBMITTED",
      editable: false,
      missing_for_submit: [],
      review_options: [
        { to_status: "UNDER_REVIEW", requires_reason: false },
        { to_status: "APPROVED", requires_reason: false },
        { to_status: "CORRECTION_REQUIRED", requires_reason: true },
        { to_status: "REJECTED", requires_reason: true },
        { to_status: "NOT_ELIGIBLE", requires_reason: true },
      ],
    });
    await show(detail());
    expect(
      screen.queryByRole("link", { name: /Continue application/ }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Review" }));
    let dialog = await screen.findByRole("dialog");
    await user.click(
      within(dialog).getByRole("button", { name: /New status/ }),
    );
    await user.click(await screen.findByRole("option", { name: "Approve" }));
    await user.click(
      within(dialog).getByRole("button", { name: "Save status" }),
    );
    expect(
      await within(dialog).findByText("Verify every document first"),
    ).toBeInTheDocument();
    await user.click(
      within(dialog).getByRole("button", { name: /New status/ }),
    );
    await user.click(await screen.findByRole("option", { name: "Reject" }));
    await user.click(
      within(dialog).getByRole("button", { name: "Save status" }),
    );
    expect(
      await within(dialog).findByText("Enter a reason."),
    ).toBeInTheDocument();
    await user.type(
      within(dialog).getByRole("textbox", { name: /Reason/ }),
      "Below the PCM requirement",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Save status" }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(api.callsTo(`POST ${APP}/review`)[1]!.body).toEqual({
      to_status: "REJECTED",
      reason: "Below the PCM requirement",
      version: 2,
    });
    dialog = screen.queryByRole("dialog") as HTMLElement;
    expect(dialog).toBeNull();
  });

  it("admission links a student only by explicit choice", async () => {
    const user = userEvent.setup();
    state.session = readySession({ permissions: ADMISSIONS_MANAGER });
    const api = installFetch();
    api.on(
      `GET ${APP}/student-candidates`,
      jsonResponse(200, { data: { candidates: [candidate()] } }),
    );
    api.on(
      `POST ${APP}/admit`,
      jsonResponse(200, { data: application({ status: "ADMITTED" }) }),
    );
    detailReads(
      { status: "APPROVED", editable: false, missing_for_submit: [] },
      [
        documentWire({
          status: "VERIFIED",
          reviewed_by: "Ananya Rao",
          reviewed_at: "2026-10-10T05:00:00Z",
        }),
      ],
    );
    await show(detail());
    await user.click(screen.getByRole("button", { name: "Approve admission" }));
    const dialog = await screen.findByRole("dialog");
    expect(
      await within(dialog).findByText("Possible existing student"),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole("radio", { name: /Create a new student/ }),
    ).toBeChecked();
    await user.click(
      within(dialog).getByRole("radio", { name: /Link to STU-2025-00031/ }),
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Approve admission" }),
    );
    await waitFor(() =>
      expect(api.callsTo(`POST ${APP}/admit`)).toHaveLength(1),
    );
    expect(api.callsTo(`POST ${APP}/admit`)[0]!.body).toEqual({
      student: "existing",
      student_id: IDS.otherStudent,
      version: 2,
    });
  });

  it("an admitted application links its student and offers no actions", async () => {
    state.session = readySession({ permissions: ADMISSIONS_MANAGER });
    detailReads({
      status: "ADMITTED",
      editable: false,
      missing_for_submit: [],
      admission: {
        id: "adm-1",
        admission_number: "ADM-2026-00007",
        student_id: IDS.student,
        student_number: "STU-2026-00007",
        student_visible: true,
      },
    });
    await show(detail());
    expect(screen.getByText("ADM-2026-00007")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "STU-2026-00007" }),
    ).toHaveAttribute("href", `/app/admissions/students/${IDS.student}`);
    for (const name of ["Review", "Approve admission", "Upload document"]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });
});

// --- Source rules -----------------------------------------------------------------------

const SRC = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../..",
);
const FILES = [
  "features/applications/AdmitDialog.tsx",
  "features/applications/ApplicationActions.tsx",
  "features/applications/ApplicationList.tsx",
  "features/applications/ApplicationWizard.tsx",
  "features/applications/StartApplicationForm.tsx",
  "features/applications/mutations.ts",
  "features/documents/DocumentsPanel.tsx",
  "features/documents/UploadDocumentDialog.tsx",
  "features/documents/DocumentQueue.tsx",
  "features/students/StudentList.tsx",
];

describe("source rules", () => {
  it("no role-name gating, storage, logging or tenant IDs from the browser", () => {
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
      expect(source, file).not.toMatch(/object_key|presigned|X-Amz/i);
    }
  });
});
