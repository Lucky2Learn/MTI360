import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectHeadingOutline } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import type { ReadResult } from "@/lib/api/server-read";
import type { SessionWire } from "@/lib/api/types";
import { ok } from "@/test/admissions-fixtures";
import { apiError, installFetch, jsonResponse } from "@/test/fetch-mock";
import {
  FIN,
  FINANCE_MANAGER,
  FINANCE_OFFICER,
  payment,
  pendingCheque,
} from "@/test/finance-fixtures";
import { readySession } from "@/test/session-fixtures";

import { TenantFrame } from "../../tenant-frame";

import PaymentPage from "./[paymentId]/page";
import ReceiptPage from "./[paymentId]/receipt/page";
import PaymentsPage from "./page";

import type { ReactElement } from "react";

vi.setConfig({ testTimeout: 30_000 });

// FIN-06 Payments, FIN-07 Payment and its receipt (Phase 02-5; ADR-0022 §4,
// §9; addendum R1): gates, the clearance flow for cheques and demand drafts,
// separation of duties on reversal (hidden for the recorder by
// `recorded_by_me`, and the server's 422 explained), the cancelled receipt,
// and the 404 for another tenant's or campus's payment.

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
  usePathname: () => "/app/finance/payments",
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
  state.session = readySession({ permissions: FINANCE_MANAGER });
  state.reads = [];
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

const detail = (id: string = FIN.cash) =>
  PaymentPage({ params: Promise.resolve({ paymentId: id }) });
const receipt = (id: string = FIN.cash) =>
  ReceiptPage({ params: Promise.resolve({ paymentId: id }) });

describe("FIN-06 Payments", () => {
  it("needs invoice.read (AUTHZ-01 at the same URL)", async () => {
    state.session = readySession({ permissions: ["payment.record"] });
    await show(PaymentsPage({ searchParams: Promise.resolve({}) }));
    expect(
      screen.getByText("You don't have access to this page"),
    ).toBeInTheDocument();
    expect(state.paths).toEqual([]);
  });

  it.each(["light", "dark"] as const)(
    "lists payments with receipts and statuses; forwards only known filters (%s)",
    async (theme) => {
      state.reads.push([
        "/payments",
        ok(
          [
            payment(),
            pendingCheque(),
            payment({
              id: "0199a1b2-0000-7000-8000-000000000f33",
              status: "REVERSED",
              receipt: { ...payment().receipt!, cancelled: true },
            }),
          ],
          3,
        ),
      ]);
      const { container } = await show(
        PaymentsPage({
          searchParams: Promise.resolve({
            status: "PENDING",
            method: "CHEQUE",
            received_from: "2026-10-01",
            invoice_id: FIN.invoice,
          }),
        }),
        theme,
      );
      const query = new URLSearchParams(state.paths[0]!.split("?")[1]);
      expect(query.get("status")).toBe("PENDING");
      expect(query.get("method")).toBe("CHEQUE");
      expect(query.get("received_from")).toBe("2026-10-01");
      expect(query.has("invoice_id")).toBe(false);
      const table = screen.getByRole("table", { name: "Payments" });
      expect(within(table).getByText("Awaiting clearance")).toBeInTheDocument();
      expect(
        within(table).getByText("RCT-FY2026-27-00031 (cancelled)"),
      ).toBeInTheDocument();
      expect(within(table).getByText("₹50,000.00")).toBeInTheDocument();
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );
});

describe("FIN-07 Payment", () => {
  it.each(["light", "dark"] as const)(
    "confirms a cheque after clearance with its version (%s)",
    async (theme) => {
      const user = userEvent.setup();
      const api = installFetch();
      api.on(
        `POST /payments/${FIN.cheque}/confirm`,
        jsonResponse(200, {
          data: pendingCheque({
            status: "CONFIRMED",
            receipt: payment().receipt,
          }),
          meta: {},
        }),
      );
      state.session = readySession({ permissions: FINANCE_OFFICER });
      state.reads.push([
        `/payments/${FIN.cheque}`,
        ok(pendingCheque({ version: 2 })),
      ]);
      const { container } = await show(detail(FIN.cheque), theme);
      expect(
        screen.getByText(/not yet in the balance and no receipt/),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          "A receipt is issued when the payment is confirmed as cleared.",
        ),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Reverse payment" }),
      ).toBeNull();
      await expectNoA11yViolations(container);
      await user.click(
        screen.getByRole("button", { name: "Confirm clearance" }),
      );
      const dialog = await screen.findByRole("alertdialog", {
        name: /Confirm the cheque/,
      });
      expect(dialog).toHaveTextContent(/balance drops by ₹50,000\.00/);
      await user.click(
        within(dialog).getByRole("button", { name: "Confirm clearance" }),
      );
      await waitFor(() =>
        expect(
          api.callsTo(`POST /payments/${FIN.cheque}/confirm`),
        ).toHaveLength(1),
      );
      expect(
        api.callsTo(`POST /payments/${FIN.cheque}/confirm`)[0]!.body,
      ).toEqual({
        version: 2,
      });
      await waitFor(() => expect(state.refresh).toHaveBeenCalled());
      await waitFor(() =>
        expect(
          screen.queryByRole("alertdialog", { name: /Confirm the cheque/ }),
        ).toBeNull(),
      );
    },
  );

  it("fails a cheque only with a reason", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    const route = `POST /payments/${FIN.cheque}/fail`;
    api.on(
      route,
      jsonResponse(200, {
        data: pendingCheque({ status: "FAILED" }),
        meta: {},
      }),
    );
    state.reads.push([`/payments/${FIN.cheque}`, ok(pendingCheque())]);
    await show(detail(FIN.cheque));
    await user.click(screen.getByRole("button", { name: "Mark as failed" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(
      within(dialog).getByRole("button", { name: "Mark as failed" }),
    );
    expect(
      await within(dialog).findByText("Enter a reason."),
    ).toBeInTheDocument();
    expect(api.callsTo(route)).toHaveLength(0);
    await user.type(
      within(dialog).getByRole("textbox", { name: /Reason/ }),
      "Cheque returned — insufficient funds",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Mark as failed" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.callsTo(route)[0]!.body).toEqual({
      reason: "Cheque returned — insufficient funds",
      version: 1,
    });
  });

  it("hides Reverse from the payment's recorder and says why", async () => {
    state.reads.push([
      `/payments/${FIN.cash}`,
      ok(payment({ recorded_by_me: true })),
    ]);
    await show(detail());
    expect(
      screen.queryByRole("button", { name: "Reverse payment" }),
    ).toBeNull();
    expect(
      screen.getByText(
        /You recorded this payment\. A payment is reversed by someone other/,
      ),
    ).toBeInTheDocument();
  });

  it("reverses with a reason, and explains the server's recorder_cannot_reverse (422)", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    const route = `POST /payments/${FIN.cash}/reverse`;
    api.on(
      route,
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "payment", code: "recorder_cannot_reverse" }],
      }),
      jsonResponse(200, { data: payment({ status: "REVERSED" }), meta: {} }),
    );
    state.reads.push([`/payments/${FIN.cash}`, ok(payment())]);
    const { container } = await show(detail());
    await user.click(screen.getByRole("button", { name: "Reverse payment" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(
      /receipt RCT-FY2026-27-00031 stays on record, shown as cancelled/,
    );
    await user.type(
      within(dialog).getByRole("textbox", { name: /Reason for the reversal/ }),
      "Recorded against the wrong student",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Reverse payment" }),
    );
    expect(
      await within(dialog).findByText("You can't reverse your own payment"),
    ).toBeInTheDocument();
    expect(container.textContent).not.toContain("SERVER-");
    await user.click(
      within(dialog).getByRole("button", { name: "Reverse payment" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.callsTo(route)[1]!.body).toEqual({
      reason: "Recorded against the wrong student",
      version: 1,
    });
  });

  it("offers no actions to a reader and refreshes on a stale version", async () => {
    state.session = readySession({ permissions: ["invoice.read"] });
    state.reads.push([`/payments/${FIN.cheque}`, ok(pendingCheque())]);
    await show(detail(FIN.cheque));
    expect(
      screen.queryByRole("button", { name: "Confirm clearance" }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: "Mark as failed" })).toBeNull();

    const user = userEvent.setup();
    const api = installFetch();
    api.on(`POST /payments/${FIN.cheque}/confirm`, apiError(409, "CONFLICT"));
    state.session = readySession({ permissions: FINANCE_OFFICER });
    await show(detail(FIN.cheque));
    await user.click(screen.getByRole("button", { name: "Confirm clearance" }));
    await user.click(
      within(
        await screen.findByRole("alertdialog", { name: /Confirm the cheque/ }),
      ).getByRole("button", {
        name: "Confirm clearance",
      }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
  });

  it("another tenant's or campus's, or a malformed, payment is not found", async () => {
    state.reads.push([`/payments/${FIN.cash}`, { kind: "not-found" }]);
    await expect(detail()).rejects.toThrow("NEXT_NOT_FOUND");
    await expect(detail("RCT-FY2026-27-00031")).rejects.toThrow(
      "NEXT_NOT_FOUND",
    );
    await expect(receipt()).rejects.toThrow("NEXT_NOT_FOUND");
  });
});

describe("FIN-07 Receipt", () => {
  it.each(["light", "dark"] as const)(
    "prints the receipt in one region; a reversed payment's receipt prints as cancelled (%s)",
    async (theme) => {
      state.reads.push([
        `/payments/${FIN.cash}`,
        ok(
          payment({
            status: "REVERSED",
            status_reason: "Recorded against the wrong student",
            receipt: { ...payment().receipt!, cancelled: true },
          }),
        ),
      ]);
      const { container } = await show(receipt(), theme);
      const region = container.querySelector("[data-print-region]");
      expect(region).toHaveTextContent("Receipt RCT-FY2026-27-00031");
      expect(region).toHaveTextContent("Coastal Maritime Training Institute");
      expect(region).toHaveTextContent(
        "CANCELLED — this payment was reversed: Recorded against the wrong student",
      );
      expect(region).toHaveTextContent("₹1,00,000.00");
      expect(container.querySelector("[data-print-hide]")).toContainElement(
        screen.getByRole("button", { name: "Print receipt" }),
      );
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("explains that a cheque awaiting clearance has no receipt yet", async () => {
    state.reads.push([`/payments/${FIN.cheque}`, ok(pendingCheque())]);
    await show(receipt(FIN.cheque));
    expect(
      screen.getByRole("heading", { name: "No receipt for this payment" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/issued when the cheque or demand draft is confirmed/),
    ).toBeInTheDocument();
    expect(document.querySelector("[data-print-region]")).toBeNull();
  });
});
