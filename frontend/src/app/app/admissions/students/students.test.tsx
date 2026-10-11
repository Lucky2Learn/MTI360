import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectHeadingOutline } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import type { ReadResult } from "@/lib/api/server-read";
import type { SessionWire } from "@/lib/api/types";
import {
  ADMISSIONS_COUNSELLOR,
  IDS,
  ok,
  student,
  studentItem,
  timelineEntry,
} from "@/test/admissions-fixtures";
import { FIN, FINANCE_OFFICER, invoice } from "@/test/finance-fixtures";
import { readySession } from "@/test/session-fixtures";

import { TenantFrame } from "../../tenant-frame";

import StudentPage from "./[studentId]/page";
import StudentsPage from "./page";

import type { ReactElement } from "react";

vi.setConfig({ testTimeout: 30_000 });

// ADM-11 Students and ADM-12 Student 360 with ADM-13 admissions and ADM-14
// documents (Phase 02-2; ADR-0021 §6, §14): gates, states, sections, the
// intentional empty state for modules that do not exist yet, and a timeline
// that labels enquiry and application history.

const state = vi.hoisted(() => ({
  session: null as SessionWire | null,
  reads: [] as [string, ReadResult<unknown>][],
  paths: [] as string[],
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/app/admissions/students",
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
  state.reads = [];
  state.paths = [];
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
  StudentsPage({ searchParams: Promise.resolve(search) });
const profile = () =>
  StudentPage({ params: Promise.resolve({ studentId: IDS.student }) });
const S = `/students/${IDS.student}`;

function profileReads() {
  state.reads.unshift(
    [
      `${S}/documents`,
      ok({
        items: [
          {
            id: IDS.passport,
            application_id: IDS.application,
            application_number: "APP-2026-00012",
            document_type: "PASSPORT",
            status: "VERIFIED",
            file_name: "arjun-passport.pdf",
            content_type: "application/pdf",
            size_bytes: 482000,
            created_at: "2026-10-09T05:30:00Z",
          },
        ],
      }),
    ],
    [
      `${S}/activity`,
      ok(
        [
          timelineEntry(),
          timelineEntry({
            id: "tl-2",
            source: "lead",
            kind: "CREATED",
            details: { source: "WALK_IN", possible_duplicates: 0 },
            created_at: "2026-10-01T05:00:00Z",
          }),
          timelineEntry({
            id: "tl-3",
            source: "lead",
            kind: "NOTE",
            details: {},
            body: "Father sails as Chief Engineer.",
            created_at: "2026-10-02T05:00:00Z",
          }),
        ],
        3,
      ),
    ],
    [S, ok(student())],
  );
}

describe("ADM-11 Students", () => {
  it("needs a session, then student.read", async () => {
    state.session = null;
    await expect(list()).rejects.toThrow(
      "NEXT_REDIRECT /session-ended?next=/app/admissions/students",
    );
    state.session = readySession({ permissions: ["lead.read"] });
    await show(list());
    expect(
      screen.getByText("You don't have access to this page"),
    ).toBeInTheDocument();
  });

  it.each(["light", "dark"] as const)(
    "lists students and passes axe (%s)",
    async (theme) => {
      state.reads.unshift(["/students", ok([studentItem()], 1)]);
      const { container } = await show(list(), theme);
      const table = screen.getByRole("table", { name: "Students" });
      expect(
        within(table).getByRole("link", { name: "Arjun Nair" }),
      ).toHaveAttribute("href", `/app/admissions/students/${IDS.student}`);
      expect(within(table).getByText("STU-2026-00007")).toBeInTheDocument();
      expect(
        screen.queryByRole("link", { name: /New student/ }),
      ).not.toBeInTheDocument();
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("explains that students come from admissions; forwards only known filters", async () => {
    state.reads.unshift(["/students", ok([], 0)]);
    await show(list({ campus: "x", tenant_id: "y", q: "arjun" }));
    const read = state.paths.find((p) => p.startsWith("/students?")) ?? "";
    const query = new URLSearchParams(read.split("?")[1]);
    expect(query.get("q")).toBe("arjun");
    expect(query.has("campus")).toBe(false);
    expect(query.has("tenant_id")).toBe(false);
    expect(
      screen.getAllByText(
        "Students are created when an admission is approved on an application.",
      ).length,
    ).toBeGreaterThan(0);
  });
});

describe("ADM-12 Student 360", () => {
  it.each(["light", "dark"] as const)(
    "shows personal details, admissions, documents and the labelled history (%s)",
    async (theme) => {
      profileReads();
      const { container } = await show(profile(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "Arjun Nair" }),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          "ADM-2026-00007 · Pre-sea · Kochi Campus · 12 Oct 2026",
        ),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "Application APP-2026-00012" }),
      ).toHaveAttribute(
        "href",
        `/app/admissions/applications/${IDS.application}`,
      );
      expect(
        screen.getByRole("link", { name: /arjun-passport\.pdf/ }),
      ).toHaveAttribute("href", `/api/v1/documents/${IDS.passport}/download`);
      expect(screen.getByText("Coming with later modules")).toBeInTheDocument();
      const history = screen.getByRole("list", { name: "Student history" });
      expect(
        within(history).getByText(/Application: Admission approved/),
      ).toBeInTheDocument();
      expect(
        within(history).getByText(/Enquiry: Lead created/),
      ).toBeInTheDocument();
      expect(
        within(history).getByText("Father sails as Chief Engineer."),
      ).toBeInTheDocument();
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("without document.read no documents are read or shown", async () => {
    state.session = readySession({ permissions: ["student.read"] });
    profileReads();
    state.reads.unshift([`${S}/activity`, ok([], 0)]);
    await show(profile());
    expect(state.paths.some((p) => p.endsWith("/documents"))).toBe(false);
    expect(
      screen.queryByRole("heading", { name: "Documents" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("No history to show")).toBeInTheDocument();
  });

  it("another campus's or a malformed student is not found", async () => {
    state.reads.unshift(
      [S, { kind: "not-found" }],
      [`${S}/activity`, { kind: "not-found" }],
      [`${S}/documents`, { kind: "not-found" }],
    );
    await expect(profile()).rejects.toThrow("NEXT_NOT_FOUND");
    await expect(
      StudentPage({ params: Promise.resolve({ studentId: "STU-2026-00007" }) }),
    ).rejects.toThrow("NEXT_NOT_FOUND");
  });
});

describe("ADM-12 Student 360 Fees (Phase 02-5; ADR-0022 addendum R2)", () => {
  it.each(["light", "dark"] as const)(
    "lists the student's fee invoices from GET /invoices?student_id=, never a student-fees route (%s)",
    async (theme) => {
      state.session = readySession({ permissions: FINANCE_OFFICER });
      profileReads();
      state.reads.unshift([
        "/invoices",
        ok(
          [invoice({ admission: { id: "adm-1", number: "ADM-2026-00007" } })],
          1,
        ),
      ]);
      const { container } = await show(profile(), theme);
      const read = state.paths.find((p) => p.startsWith("/invoices"))!;
      const query = new URLSearchParams(read.split("?")[1]);
      expect(query.get("student_id")).toBe(IDS.student);
      expect(state.paths.some((p) => p.includes("/fees"))).toBe(false);
      const fees = screen.getByRole("list", { name: "Fee invoices" });
      expect(
        within(fees).getByRole("link", { name: "INV-FY2026-27-00012" }),
      ).toHaveAttribute("href", `/app/finance/invoices/${FIN.invoice}`);
      expect(within(fees).getByText("₹1,53,500.00")).toBeInTheDocument();
      expect(
        within(fees).getByRole("link", {
          name: "Record payment on INV-FY2026-27-00012",
        }),
      ).toHaveAttribute("href", `/app/finance/invoices/${FIN.invoice}?pay=1`);
      // The admission already has a live fee invoice: nothing to raise.
      expect(
        screen.queryByRole("link", { name: /Raise fee invoice/ }),
      ).toBeNull();
      expect(
        screen.getByText(/Training, Exams, Certificates/),
      ).not.toHaveTextContent("Fees");
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("offers Raise fee invoice for an admission without a live one; empty says only what is visible", async () => {
    state.session = readySession({ permissions: FINANCE_OFFICER });
    profileReads();
    state.reads.unshift(["/invoices", ok([], 0)]);
    await show(profile());
    expect(screen.getByText("No fee invoices")).toBeInTheDocument();
    expect(
      screen.getByText(/at your campuses appear here/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: "Raise fee invoice for ADM-2026-00007",
      }),
    ).toHaveAttribute(
      "href",
      `/app/finance/invoices/new?student=${IDS.student}&admission=adm-1`,
    );
  });

  it("reads no fees without invoice.read, and shows a failed read as an error state", async () => {
    profileReads();
    await show(profile());
    expect(state.paths.some((p) => p.startsWith("/invoices"))).toBe(false);
    expect(screen.queryByRole("heading", { name: "Fees" })).toBeNull();

    state.session = readySession({
      permissions: ["student.read", "invoice.read"],
    });
    state.paths = [];
    state.reads.unshift([
      "/invoices",
      { kind: "error", reference: "req-5521" },
    ]);
    await show(profile());
    expect(
      screen.getByRole("heading", { name: "Fees couldn't be loaded" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /Raise fee invoice/ }),
    ).toBeNull();
  });
});
