import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectHeadingOutline } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import { istToday } from "@/features/finance/today";
import type { ReadResult } from "@/lib/api/server-read";
import type { SessionWire } from "@/lib/api/types";
import { IDS, ok, student } from "@/test/admissions-fixtures";
import { apiError, installFetch, jsonResponse } from "@/test/fetch-mock";
import {
  feeStructure,
  FIN,
  FINANCE_MANAGER,
  FINANCE_OFFICER,
  invoice,
  invoiceDetail,
  payment,
  pendingCheque,
  summary,
} from "@/test/finance-fixtures";
import { CAMPUSES, readySession } from "@/test/session-fixtures";

import { TenantFrame } from "../../tenant-frame";
import OutstandingPage from "../outstanding/page";

import InvoicePage from "./[invoiceId]/page";
import PrintInvoicePage from "./[invoiceId]/print/page";
import IssueInvoicePage from "./new/page";
import InvoicesPage from "./page";

import type { ReactElement } from "react";

vi.setConfig({ testTimeout: 30_000 });

// FIN-04 Fee invoices, FIN-05 Fee invoice (record payment, cancel, print),
// the issue form and FIN-08 Outstanding (Phase 02-5; ADR-0022, addendum R1-R3;
// readiness plan §4, §9): gates, states, permission-gated actions, exact
// paise, the idempotency key in the JSON body and reused on retry, and the
// 409/422 mapping. Server messages are never shown.

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const READER = ["invoice.read", "student.read"];

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
  usePathname: () => "/app/finance/invoices",
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
  InvoicesPage({ searchParams: Promise.resolve(search) });
const detail = (
  search: Record<string, string> = {},
  id: string = FIN.invoice,
) =>
  InvoicePage({
    params: Promise.resolve({ invoiceId: id }),
    searchParams: Promise.resolve(search),
  });
const issue = (search: Record<string, string>) =>
  IssueInvoicePage({ searchParams: Promise.resolve(search) });
const queryOf = (index = 0) =>
  new URLSearchParams(state.paths[index]!.split("?")[1]);

async function typeDate(
  user: ReturnType<typeof userEvent.setup>,
  label: string,
  ddmmyyyy: string,
) {
  const group = screen.getByRole("group", { name: new RegExp(label) });
  await user.click(within(group).getAllByRole("spinbutton")[0]!);
  await user.keyboard(ddmmyyyy);
}

describe("FIN-04 Fee invoices", () => {
  it("needs a session, then invoice.read (AUTHZ-01 at the same URL)", async () => {
    state.session = null;
    await expect(list()).rejects.toThrow(
      "NEXT_REDIRECT /session-ended?next=/app/finance/invoices",
    );
    state.session = readySession({ permissions: ["fee_structure.read"] });
    await show(list());
    expect(
      screen.getByRole("heading", {
        name: "You don't have access to this page",
      }),
    ).toBeInTheDocument();
    expect(state.paths).toEqual([]);
  });

  it.each(["light", "dark"] as const)(
    "lists fee invoices with exact balances and text statuses, and passes axe (%s)",
    async (theme) => {
      state.reads.push(
        ["/courses", ok([], 0)],
        [
          "/invoices",
          ok(
            [
              invoice(),
              invoice({
                id: FIN.otherInvoice,
                number: "INV-FY2026-27-00013",
                status: "ISSUED",
                paid_minor: 0,
                balance_minor: 25_350_050,
                overdue: true,
              }),
            ],
            2,
          ),
        ],
      );
      const { container } = await show(list(), theme);
      const table = screen.getByRole("table", { name: "Fee invoices" });
      expect(
        within(table).getByRole("link", { name: "INV-FY2026-27-00012" }),
      ).toHaveAttribute("href", `/app/finance/invoices/${FIN.invoice}`);
      expect(within(table).getByText("₹1,53,500.00")).toBeInTheDocument();
      expect(within(table).getByText("₹2,53,500.50")).toBeInTheDocument();
      expect(within(table).getByText("Partly paid")).toBeInTheDocument();
      expect(within(table).getByText("Overdue")).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "Raise fee invoice" }),
      ).toHaveAttribute("href", "/app/admissions/students");
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("forwards only known filters; a reader without invoice.issue gets no Raise action", async () => {
    state.session = readySession({ permissions: READER });
    state.reads.push(["/invoices", ok([], 0)]);
    await show(
      list({
        q: "INV-FY2026",
        status: "PARTIALLY_PAID",
        overdue: "true",
        due_from: "2026-10-01",
        due_to: "31/10/2026",
        campus_id: CAMPUSES.kochi.id,
        student_id: IDS.otherStudent,
        tenant_id: "x",
        sort: "-balance",
      }),
    );
    expect(state.paths.some((p) => p.startsWith("/courses"))).toBe(false);
    const query = queryOf();
    expect(query.get("q")).toBe("INV-FY2026");
    expect(query.get("status")).toBe("PARTIALLY_PAID");
    expect(query.get("overdue")).toBe("true");
    expect(query.get("due_from")).toBe("2026-10-01");
    expect(query.get("campus_id")).toBe(CAMPUSES.kochi.id);
    expect(query.get("sort")).toBe("-balance");
    for (const dropped of [
      "due_to",
      "student_id",
      "tenant_id",
      "outstanding",
    ]) {
      expect(query.has(dropped)).toBe(false);
    }
    expect(
      screen.queryByRole("link", { name: "Raise fee invoice" }),
    ).toBeNull();
    expect(
      screen.getAllByText(/They appear here once your finance team issues them/)
        .length,
    ).toBeGreaterThan(0);
  });

  it("shows the error state with the support reference", async () => {
    state.reads.push(
      ["/courses", ok([], 0)],
      ["/invoices", { kind: "error", reference: "req-4410" }],
    );
    await show(list());
    expect(
      screen.getByRole("heading", { name: "Fee invoices couldn't be loaded" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/req-4410/)).toBeInTheDocument();
  });
});

describe("FIN-05 Fee invoice", () => {
  it.each(["light", "dark"] as const)(
    "shows the non-tax label, adjusted lines beside the structure, the balance and history (%s)",
    async (theme) => {
      state.reads.push([
        `/invoices/${FIN.invoice}`,
        ok(
          invoiceDetail({
            adjusted: true,
            total_minor: 23_500_000,
            balance_minor: 13_500_000,
            adjustment_reason: "Merit scholarship approved by the principal.",
            lines: [
              {
                position: 1,
                fee_head: "Tuition",
                amount_minor: 16_650_000,
                structure_amount_minor: 18_500_000,
                adjusted: true,
              },
              {
                position: 2,
                fee_head: "Hostel",
                amount_minor: 6_000_000,
                structure_amount_minor: 6_000_000,
                adjusted: false,
              },
              {
                position: 3,
                fee_head: "Uniform",
                amount_minor: 850_000,
                structure_amount_minor: 850_000,
                adjusted: false,
              },
            ],
          }),
        ),
      ]);
      const { container } = await show(detail(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "INV-FY2026-27-00012" }),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Fee invoice — not a tax invoice"),
      ).toBeInTheDocument();
      const lines = screen.getByRole("table", {
        name: "Fee heads and amounts",
      });
      expect(within(lines).getByText("Adjusted")).toBeInTheDocument();
      expect(within(lines).getByText("₹1,85,000.00")).toBeInTheDocument();
      expect(within(lines).getByText("₹1,66,500.00")).toBeInTheDocument();
      expect(
        screen.getByText(/Merit scholarship approved by the principal\./),
      ).toBeInTheDocument();
      const balance = screen.getByRole("complementary", {
        name: "Balance and details",
      });
      expect(within(balance).getByText("₹1,35,000.00")).toBeInTheDocument();
      expect(
        screen.getByRole("list", { name: "Fee invoice history" }),
      ).toHaveTextContent("Fee invoice issued");
      expect(
        screen.getByRole("link", { name: "Receipt RCT-FY2026-27-00031" }),
      ).toHaveAttribute("href", `/app/finance/payments/${FIN.cash}/receipt`);
      expect(
        screen.getByRole("button", { name: "Record payment" }),
      ).toBeVisible();
      expect(
        screen.getByRole("button", { name: "Cancel fee invoice" }),
      ).toBeVisible();
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("offers only Print to a reader, and nothing to pay on a paid or cancelled invoice", async () => {
    state.session = readySession({ permissions: READER });
    state.reads.push([`/invoices/${FIN.invoice}`, ok(invoiceDetail())]);
    await show(detail());
    expect(screen.getByRole("link", { name: "Print" })).toHaveAttribute(
      "href",
      `/app/finance/invoices/${FIN.invoice}/print`,
    );
    expect(screen.queryByRole("button", { name: "Record payment" })).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Cancel fee invoice" }),
    ).toBeNull();

    state.session = readySession({ permissions: FINANCE_MANAGER });
    state.reads = [
      [
        `/invoices/${FIN.invoice}`,
        ok(
          invoiceDetail({
            status: "CANCELLED",
            balance_minor: 0,
            paid_minor: 0,
            status_reason: "Replaced: wrong course on the admission.",
            payments: [],
          }),
        ),
      ],
    ];
    await show(detail());
    expect(
      screen.getByText("Reason: Replaced: wrong course on the admission."),
    ).toBeInTheDocument();
    expect(screen.queryAllByRole("button", { name: "Record payment" })).toEqual(
      [],
    );
  });

  it("another tenant's or campus's, or a malformed, fee invoice is not found", async () => {
    state.reads.push([`/invoices/${FIN.invoice}`, { kind: "not-found" }]);
    await expect(detail()).rejects.toThrow("NEXT_NOT_FOUND");
    await expect(detail({}, "INV-FY2026-27-00012")).rejects.toThrow(
      "NEXT_NOT_FOUND",
    );
  });
});

describe("FIN-05 Record payment", () => {
  it("sends integer paise and the idempotency key in the JSON body, and reuses the key on retry", async () => {
    const user = userEvent.setup();
    const consoleSpies = (["log", "info", "warn", "error"] as const).map(
      (method) => vi.spyOn(console, method),
    );
    const api = installFetch();
    const route = `POST /invoices/${FIN.invoice}/payments`;
    api.on(
      route,
      new TypeError("Failed to fetch"),
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "amount_minor", code: "exceeds_balance" }],
      }),
      jsonResponse(201, {
        data: payment({ id: FIN.cash, method: "UPI", amount_minor: 5_000_050 }),
        meta: {},
      }),
    );
    state.reads.push([
      `/invoices/${FIN.invoice}`,
      ok(invoiceDetail({ pending_minor: 5_000_000 })),
    ]);
    const { container } = await show(detail());
    await user.click(screen.getByRole("button", { name: "Record payment" }));
    const dialog = await screen.findByRole("dialog");
    // Balance ₹1,53,500 less a ₹50,000 cheque awaiting clearance.
    expect(dialog).toHaveTextContent("Up to ₹1,03,500.00 can be recorded.");

    await user.type(
      within(dialog).getByRole("textbox", { name: /Amount/ }),
      "50000.005",
    );
    await user.click(
      within(dialog).getByRole("button", { name: /Payment method/ }),
    );
    await user.click(await screen.findByRole("option", { name: "UPI" }));
    await user.click(
      within(dialog).getByRole("button", { name: "Record payment" }),
    );
    expect(
      await within(dialog).findByText(
        "Enter an amount in rupees, e.g. 25000 or 1,25,000.50.",
      ),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText("Enter the reference for this payment method."),
    ).toBeInTheDocument();
    expect(api.callsTo(route)).toHaveLength(0);

    const amount = within(dialog).getByRole("textbox", { name: /Amount/ });
    await user.clear(amount);
    await user.type(amount, "50,000.50");
    await user.type(
      within(dialog).getByRole("textbox", { name: /UPI transaction ID/ }),
      "UPI 4521 8890 1123",
    );
    // 1: no response (network) → generic feedback; nothing changes.
    await user.click(
      within(dialog).getByRole("button", { name: "Record payment" }),
    );
    expect(
      await within(dialog).findByText("Something went wrong"),
    ).toBeInTheDocument();
    // 2: the retry carries the same key; the server's 422 maps to the field.
    await user.click(
      within(dialog).getByRole("button", { name: "Record payment" }),
    );
    expect(
      await within(dialog).findByText(/more than the balance still to collect/),
    ).toBeInTheDocument();
    // 3: success.
    await user.click(
      within(dialog).getByRole("button", { name: "Record payment" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    const calls = api.callsTo(route);
    expect(calls).toHaveLength(3);
    const first = calls[0]!.body as Record<string, unknown>;
    expect(first).toEqual({
      amount_minor: 5_000_050,
      method: "UPI",
      reference: "UPI 4521 8890 1123",
      received_on: istToday(),
      idempotency_key: expect.stringMatching(UUID) as unknown,
    });
    expect(Number.isInteger(first.amount_minor)).toBe(true);
    for (const call of calls) {
      expect((call.body as Record<string, unknown>).idempotency_key).toBe(
        first.idempotency_key,
      );
      expect(Object.keys(call.headers)).not.toContain("idempotency-key");
    }
    expect(state.refresh).toHaveBeenCalled();
    expect(container.textContent).not.toContain("SERVER-");
    // No amount or reference reaches the console or browser storage.
    const stored = JSON.stringify({
      ...window.localStorage,
      ...window.sessionStorage,
    });
    for (const secret of ["4521 8890", "5000050", "50,000.50"]) {
      expect(stored).not.toContain(secret);
      for (const spy of consoleSpies) {
        expect(JSON.stringify(spy.mock.calls)).not.toContain(secret);
      }
    }
    consoleSpies.forEach((spy) => spy.mockRestore());

    // The next payment gets a new key.
    api.on(route, jsonResponse(201, { data: pendingCheque(), meta: {} }));
    await user.click(screen.getByRole("button", { name: "Record payment" }));
    const next = await screen.findByRole("dialog");
    await user.type(
      within(next).getByRole("textbox", { name: /Amount/ }),
      "50000",
    );
    await user.click(
      within(next).getByRole("button", { name: /Payment method/ }),
    );
    await user.click(await screen.findByRole("option", { name: "Cheque" }));
    expect(within(next).getByText("Saved as awaiting clearance")).toBeVisible();
    await user.type(
      within(next).getByRole("textbox", { name: /Cheque number and bank/ }),
      "Cheque 004512, State Bank of India",
    );
    await user.click(
      within(next).getByRole("button", { name: "Record payment" }),
    );
    await waitFor(() => expect(api.callsTo(route)).toHaveLength(4));
    expect(
      (api.callsTo(route)[3]!.body as Record<string, unknown>).idempotency_key,
    ).not.toBe(first.idempotency_key);
  });

  it("explains a reused key (409) without resending, and opens from Student 360's link", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    const route = `POST /invoices/${FIN.invoice}/payments`;
    api.on(
      route,
      apiError(409, "CONFLICT", {
        details: [{ field: "idempotency_key", code: "idempotency_key_reused" }],
      }),
    );
    state.reads.push([`/invoices/${FIN.invoice}`, ok(invoiceDetail())]);
    await show(detail({ pay: "1" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(
      within(dialog).getByRole("textbox", { name: /Amount/ }),
      "1000",
    );
    await user.click(
      within(dialog).getByRole("button", { name: /Payment method/ }),
    );
    await user.click(await screen.findByRole("option", { name: "Cash" }));
    await user.click(
      within(dialog).getByRole("button", { name: "Record payment" }),
    );
    expect(
      await within(dialog).findByText(
        "This form was already sent with different details",
      ),
    ).toBeInTheDocument();
    expect(api.callsTo(route)).toHaveLength(1);
    expect(state.refresh).not.toHaveBeenCalled();
    expect(
      (api.callsTo(route)[0]!.body as Record<string, unknown>).reference,
    ).toBeNull();
  });
});

describe("FIN-05 Cancel fee invoice", () => {
  it("names the payments to resolve first and maps the server's refusal", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    const route = `POST /invoices/${FIN.invoice}/cancel`;
    api.on(
      route,
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "status", code: "open_payments" }],
      }),
    );
    state.reads.push([
      `/invoices/${FIN.invoice}`,
      ok(invoiceDetail({ payments: [payment(), pendingCheque()] })),
    ]);
    await show(detail());
    await user.click(
      screen.getByRole("button", { name: "Cancel fee invoice" }),
    );
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(
      /Resolve these payments first: Cash ₹1,00,000\.00 received 6 Oct 2026 \(confirmed\); Cheque ₹50,000\.00 received 8 Oct 2026 \(awaiting clearance\)/,
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Save status" }),
    );
    expect(
      await within(dialog).findByText("Enter a reason."),
    ).toBeInTheDocument();
    expect(api.callsTo(route)).toHaveLength(0);
    await user.type(
      within(dialog).getByRole("textbox", { name: /Reason/ }),
      "Admission withdrawn",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Save status" }),
    );
    expect(
      await within(dialog).findByText("Resolve the payments first"),
    ).toBeInTheDocument();
    expect(api.callsTo(route)[0]!.body).toEqual({
      reason: "Admission withdrawn",
      version: 3,
    });
  });

  it("cancels an invoice without open payments", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    const route = `POST /invoices/${FIN.invoice}/cancel`;
    api.on(
      route,
      jsonResponse(200, {
        data: invoiceDetail({ status: "CANCELLED" }),
        meta: {},
      }),
    );
    state.reads.push([
      `/invoices/${FIN.invoice}`,
      ok(
        invoiceDetail({
          status: "ISSUED",
          paid_minor: 0,
          balance_minor: 25_350_000,
          payments: [payment({ status: "REVERSED" })],
        }),
      ),
    ]);
    await show(detail());
    await user.click(
      screen.getByRole("button", { name: "Cancel fee invoice" }),
    );
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(/gets a new number/);
    await user.type(
      within(dialog).getByRole("textbox", { name: /Reason/ }),
      "Issued for the wrong admission",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Save status" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(state.refresh).toHaveBeenCalled();
  });
});

describe("FIN-05 Print view", () => {
  it("prints the institute from the session, the non-tax label and the lines, as one print region", async () => {
    state.reads.push([`/invoices/${FIN.invoice}`, ok(invoiceDetail())]);
    const { container } = await show(
      PrintInvoicePage({ params: Promise.resolve({ invoiceId: FIN.invoice }) }),
      "dark",
    );
    const region = container.querySelector("[data-print-region]");
    expect(region).not.toBeNull();
    expect(region).toHaveTextContent(state.session!.active_institute!.name);
    expect(region).toHaveTextContent("Fee invoice — not a tax invoice");
    expect(region).toHaveTextContent("Fee invoice INV-FY2026-27-00012");
    expect(region).toHaveTextContent("₹2,53,500.00");
    expect(container.querySelector("[data-print-hide]")).toContainElement(
      screen.getByRole("button", { name: "Print fee invoice" }),
    );
    await expectNoA11yViolations(container);
  });
});

describe("Issue a fee invoice", () => {
  const S = `/students/${IDS.student}`;
  const withAdmission = () =>
    student({
      admissions: [
        {
          ...student().admissions[0]!,
          id: FIN.admission,
        },
      ],
    });
  const params = { student: IDS.student, admission: FIN.admission };

  it("needs invoice.issue; without a student and admission it explains where to start", async () => {
    state.session = readySession({ permissions: READER });
    await show(issue(params));
    expect(
      screen.getByText("You don't have access to this page"),
    ).toBeInTheDocument();

    state.session = readySession({ permissions: FINANCE_OFFICER });
    await show(issue({ admission: "adm-1" }));
    expect(
      screen.getByRole("heading", { name: "Start from an admitted student" }),
    ).toBeInTheDocument();
    expect(state.paths).toEqual([]);
  });

  it("shows the live fee invoice or the missing fee structure instead of the form", async () => {
    state.session = readySession({ permissions: FINANCE_OFFICER });
    state.reads.push(
      [S, ok(withAdmission())],
      ["/fee-structures", ok([], 0)],
      [
        "/invoices",
        ok(
          [
            invoice({
              admission: { id: FIN.admission, number: "ADM-2026-00007" },
            }),
          ],
          1,
        ),
      ],
    );
    await show(issue(params));
    expect(
      screen.getByText("This admission already has a fee invoice"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open INV-FY2026-27-00012" }),
    ).toHaveAttribute("href", `/app/finance/invoices/${FIN.invoice}`);
    const invoicesRead = state.paths.find((p) => p.startsWith("/invoices"))!;
    expect(invoicesRead).toContain(`student_id=${IDS.student}`);
    expect(state.paths.some((p) => p.includes("/fees"))).toBe(false);

    state.reads = [
      [S, ok(withAdmission())],
      ["/fee-structures", ok([], 0)],
      [
        "/invoices",
        ok(
          [
            invoice({
              status: "CANCELLED",
              admission: { id: FIN.admission, number: "ADM-2026-00007" },
            }),
          ],
          1,
        ),
      ],
    ];
    await show(issue(params));
    expect(
      screen.getByText("The course has no active fee structure"),
    ).toBeInTheDocument();
  });

  it("prefills the structure, requires a reason for a change and sends exact paise with the key", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      "POST /invoices",
      apiError(409, "CONFLICT", {
        details: [{ field: "admission_id", code: "live_invoice_exists" }],
      }),
      jsonResponse(201, { data: invoiceDetail(), meta: {} }),
    );
    state.session = readySession({ permissions: FINANCE_OFFICER });
    state.reads.push(
      [S, ok(withAdmission())],
      ["/fee-structures", ok([feeStructure()], 1)],
      ["/invoices", ok([], 0)],
    );
    const { container } = await show(issue(params));
    expect(screen.getByText("Fee structure: ₹1,85,000.00")).toBeInTheDocument();
    expect(screen.getByText("₹2,53,500.00")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /Reason/ })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Issue fee invoice" }));
    expect(await screen.findByText("Choose the due date.")).toBeInTheDocument();

    const tuition = screen.getByRole("textbox", { name: /Amount for Tuition/ });
    await user.clear(tuition);
    await user.type(tuition, "1,66,500");
    await user.click(screen.getByRole("button", { name: "Add fee head" }));
    await user.type(
      screen.getByRole("textbox", { name: /Fee head 4/ }),
      "Medical",
    );
    await user.type(
      screen.getByRole("textbox", { name: /Amount 4/ }),
      "2500.50",
    );
    expect(screen.getByText("₹2,37,500.50")).toBeInTheDocument();
    await typeDate(user, "Due date", "31122099");
    await user.click(screen.getByRole("button", { name: "Issue fee invoice" }));
    expect(
      await screen.findByText(
        "Give the reason for changing the fee structure's amounts.",
      ),
    ).toBeInTheDocument();
    expect(api.callsTo("POST /invoices")).toHaveLength(0);

    await user.type(
      screen.getByRole("textbox", { name: /Reason for the change/ }),
      "Merit scholarship approved by the principal.",
    );
    await user.click(screen.getByRole("button", { name: "Issue fee invoice" }));
    expect(
      await screen.findByText("This admission already has a fee invoice"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Issue fee invoice" }));
    await waitFor(() =>
      expect(state.push).toHaveBeenCalledWith(
        `/app/finance/invoices/${FIN.invoice}`,
      ),
    );
    const [first, second] = api.callsTo("POST /invoices");
    expect(first!.body).toEqual({
      admission_id: FIN.admission,
      due_date: "2099-12-31",
      lines: [
        { fee_head: "Tuition", amount_minor: 16_650_000 },
        { fee_head: "Hostel", amount_minor: 6_000_000 },
        { fee_head: "Uniform", amount_minor: 850_000 },
        { fee_head: "Medical", amount_minor: 250_050 },
      ],
      adjustment_reason: "Merit scholarship approved by the principal.",
      idempotency_key: expect.stringMatching(UUID) as unknown,
    });
    expect((second!.body as { idempotency_key: string }).idempotency_key).toBe(
      (first!.body as { idempotency_key: string }).idempotency_key,
    );
    expect(container.textContent).not.toContain("SERVER-");
  });
});

describe("FIN-08 Outstanding", () => {
  it.each(["light", "dark"] as const)(
    "shows the server's summary strip over unpaid fee invoices, and passes axe (%s)",
    async (theme) => {
      state.reads.push(
        ["/finance/summary", ok(summary())],
        ["/courses", ok([], 0)],
        ["/invoices", ok([invoice({ overdue: true })], 1)],
      );
      const { container } = await show(
        OutstandingPage({
          searchParams: Promise.resolve({
            status: "PAID",
            campus_id: CAMPUSES.kochi.id,
          }),
        }),
        theme,
      );
      const strip = screen.getByRole("region", { name: "Summary" });
      expect(within(strip).getByText("₹8,50,000.00")).toBeInTheDocument();
      expect(within(strip).getByText("₹3,00,000.00")).toBeInTheDocument();
      expect(
        within(strip).getByText(/1 cheque or demand draft not yet/),
      ).toBeInTheDocument();
      const invoicesRead = state.paths.find((p) => p.startsWith("/invoices"))!;
      const query = new URLSearchParams(invoicesRead.split("?")[1]);
      expect(query.get("outstanding")).toBe("true");
      expect(query.has("status")).toBe(false);
      expect(query.get("sort")).toBe("due_date");
      expect(state.paths).toContain(
        `/finance/summary?campus_id=${CAMPUSES.kochi.id}`,
      );
      expect(
        screen.getByRole("table", { name: "Outstanding fee invoices" }),
      ).toBeInTheDocument();
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("is AUTHZ-01 without invoice.read and says when nothing is outstanding", async () => {
    state.session = readySession({ permissions: ["student.read"] });
    await show(OutstandingPage({ searchParams: Promise.resolve({}) }));
    expect(
      screen.getByText("You don't have access to this page"),
    ).toBeInTheDocument();

    state.session = readySession({ permissions: READER });
    state.reads.push(
      ["/finance/summary", ok(summary({ outstanding_count: 0 }))],
      ["/invoices", ok([], 0)],
    );
    await show(OutstandingPage({ searchParams: Promise.resolve({}) }));
    expect(screen.getAllByText("Nothing outstanding").length).toBeGreaterThan(
      0,
    );
  });
});
