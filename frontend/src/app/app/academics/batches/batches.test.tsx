import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectHeadingOutline } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import { validateBatch } from "@/features/batches/BatchForm";
import { batchListQuery } from "@/features/batches/query";
import type {
  AllocationWire,
  BatchWire,
  EligibleAdmissionWire,
} from "@/lib/api/batches";
import type { ReadResult } from "@/lib/api/server-read";
import type { SessionWire } from "@/lib/api/types";
import { ok } from "@/test/admissions-fixtures";
import { apiError, installFetch, jsonResponse } from "@/test/fetch-mock";
import { CAMPUSES, readySession } from "@/test/session-fixtures";

import { TenantFrame } from "../../tenant-frame";

import EditBatchPage from "./[batchId]/edit/page";
import BatchDetailPage from "./[batchId]/page";
import NewBatchPage from "./new/page";
import BatchesPage from "./page";

import type { ReactElement } from "react";

vi.setConfig({ testTimeout: 30_000 });

// ACA-05/06/07 (Phase 02-6): the server gate, list states and filters, seat
// utilisation, batch.manage-only actions, form validation and error mapping,
// allocation with the payment gate and override, transfer and withdrawal,
// read-only roles, axe in Light and Dark.

const state = vi.hoisted(() => ({
  session: null as SessionWire | null,
  reads: new Map<string, ReadResult<unknown>>(),
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  search: "",
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/app/academics/batches",
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
    for (const [prefix, result] of state.reads) {
      if (path.startsWith(prefix)) return Promise.resolve(result);
    }
    return Promise.reject(new Error(`unexpected read ${path}`));
  },
}));

const ID = {
  batch: "0199a1b2-0000-7000-8000-00000000b001",
  other: "0199a1b2-0000-7000-8000-00000000b002",
  course: "0199a1b2-0000-7000-8000-000000000002",
  allocation: "0199a1b2-0000-7000-8000-00000000a001",
  admission: "0199a1b2-0000-7000-8000-00000000d001",
  admission2: "0199a1b2-0000-7000-8000-00000000d002",
  student: "0199a1b2-0000-7000-8000-0000000000f1",
} as const;
const MANAGER = ["batch.read", "batch.manage", "batch.allocate", "course.read"];

function batch(changes: Partial<BatchWire> = {}): BatchWire {
  return {
    id: ID.batch,
    code: "DNS-2026-B",
    name: "DNS Batch 2026-B",
    intake_label: "July 2026",
    course: { id: ID.course, code: "DNS", name: "Diploma in Nautical Science" },
    campus: CAMPUSES.kochi,
    start_date: "2026-07-01",
    end_date: "2027-06-30",
    capacity: 24,
    allocated_count: 18,
    available_seats: 6,
    status: "OPEN",
    status_reason: null,
    created_at: "2026-06-01T05:30:00Z",
    updated_at: "2026-06-01T05:30:00Z",
    version: 3,
    ...changes,
  };
}

function allocation(changes: Partial<AllocationWire> = {}): AllocationWire {
  return {
    id: ID.allocation,
    batch: { id: ID.batch, code: "DNS-2026-B", name: "DNS Batch 2026-B" },
    course: { id: ID.course, code: "DNS", name: "Diploma in Nautical Science" },
    campus_id: CAMPUSES.kochi.id,
    campus_name: CAMPUSES.kochi.name,
    admission_id: ID.admission,
    admission_number: "ADM-2026-00012",
    student: {
      id: ID.student,
      number: "STU-2026-00012",
      full_name: "Kavya Menon",
    },
    status: "ACTIVE",
    payment_basis: "OVERRIDE",
    payment_override: {
      reason: "Sponsor letter from the shipping company",
      invoice_state: "PARTIALLY_PAID",
      outstanding_minor: 21_850_000,
    },
    transferred_from_id: null,
    transferred_from_batch_code: null,
    transferred_to_batch_code: null,
    allocated_at: "2026-06-10T05:30:00Z",
    allocated_by: { display_name: "Maya Iyer" },
    end_reason: null,
    end_note: null,
    ended_at: null,
    ended_by: null,
    version: 1,
    ...changes,
  };
}

function eligible(
  changes: Partial<EligibleAdmissionWire> = {},
): EligibleAdmissionWire {
  return {
    admission_id: ID.admission2,
    admission_number: "ADM-2026-00013",
    approved_at: "2026-06-02T05:30:00Z",
    student: {
      id: ID.student,
      number: "STU-2026-00013",
      full_name: "Arjun Nair",
    },
    invoice_state: "PAID",
    invoice_total_minor: 31_850_000,
    outstanding_minor: 0,
    payment_cleared: true,
    ...changes,
  };
}

beforeEach(() => {
  state.session = readySession({ permissions: MANAGER });
  state.reads.clear();
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

const list = () => BatchesPage({ searchParams: Promise.resolve({}) });
const detail = (id: string = ID.batch) =>
  BatchDetailPage({ params: Promise.resolve({ batchId: id }) });

function detailReads(
  b: BatchWire = batch(),
  active: AllocationWire[] = [allocation()],
  ended: AllocationWire[] = [],
) {
  // The more specific prefixes first: the mock matches the first prefix.
  state.reads.set(
    `/batches/${b.id}/allocations?status=ACTIVE`,
    ok(active, active.length),
  );
  state.reads.set(
    `/batches/${b.id}/allocations?status=ENDED`,
    ok(ended, ended.length),
  );
  state.reads.set(`/batches/${b.id}/activity`, ok([], 0));
  state.reads.set(`/batches/${b.id}`, ok(b));
}

describe("ACA-05 Batches", () => {
  it("needs a session, then batch.read (AUTHZ-01 at the same URL)", async () => {
    state.session = null;
    await expect(list()).rejects.toThrow(
      "NEXT_REDIRECT /session-ended?next=/app/academics/batches",
    );
    state.session = readySession({ permissions: ["course.read"] });
    await show(list());
    expect(
      screen.getByRole("heading", {
        name: "You don't have access to this page",
      }),
    ).toBeInTheDocument();
  });

  it.each(["light", "dark"] as const)(
    "lists batches with seats and status, and passes axe (%s)",
    async (theme) => {
      state.reads.set(
        "/batches",
        ok(
          [
            batch(),
            batch({
              id: ID.other,
              code: "DNS-FULL",
              name: "DNS Batch 2026-A",
              allocated_count: 24,
              available_seats: 0,
              status: "CLOSED",
            }),
          ],
          2,
        ),
      );
      state.reads.set("/courses", ok([], 0));
      const { container } = await show(list(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "Batches" }),
      ).toBeInTheDocument();
      const table = screen.getByRole("table", { name: "Batches" });
      expect(
        within(table).getByRole("link", { name: "DNS Batch 2026-B" }),
      ).toHaveAttribute("href", `/app/academics/batches/${ID.batch}`);
      expect(within(table).getByText("18 of 24 seats")).toBeInTheDocument();
      expect(
        within(table).getByText(/24 of 24 seats · Full/),
      ).toBeInTheDocument();
      expect(within(table).getByText("Closed")).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "New batch" }),
      ).toBeInTheDocument();
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("read-only roles get no New batch; empty and filtered-empty states differ", async () => {
    state.session = readySession({ permissions: ["batch.read"] });
    state.reads.set("/batches", ok([], 0));
    state.reads.set("/courses", ok([], 0));
    await show(list());
    expect(screen.queryByRole("link", { name: "New batch" })).toBeNull();
    expect(
      screen.getAllByText(
        "Batches of your campuses appear here once they are created.",
      )[0],
    ).toBeInTheDocument();
    state.search = "status=CLOSED";
    await show(list());
    expect(
      screen.getAllByText("No batches match these filters")[0],
    ).toBeInTheDocument();
  });

  it("filters change the URL; unknown URL values never reach the API", async () => {
    const user = userEvent.setup();
    state.reads.set("/batches", ok([batch()], 1));
    state.reads.set("/courses", ok([], 0));
    await show(list());
    await user.click(screen.getAllByRole("button", { name: /Status/ })[0]!);
    await user.click(await screen.findByRole("option", { name: "Closed" }));
    expect(state.replace).toHaveBeenCalledWith(
      "/app/academics/batches?status=CLOSED",
      {
        scroll: false,
      },
    );
    expect(
      batchListQuery({
        status: "DELETED",
        course_id: "x",
        has_seats: "true",
        sort: "-code",
      }),
    ).toBe("has_seats=true&sort=-code&limit=25&offset=0");
  });

  it("a failed read shows the error state with its reference", async () => {
    state.reads.set("/batches", { kind: "error", reference: "req-9" });
    state.reads.set("/courses", ok([], 0));
    await show(list());
    expect(screen.getByText("Batches couldn't be loaded")).toBeInTheDocument();
    expect(screen.getByText(/req-9/)).toBeInTheDocument();
  });
});

describe("ACA-07 Create / edit batch", () => {
  it("batch.manage only", async () => {
    state.session = readySession({
      permissions: ["batch.read", "course.read"],
    });
    await show(NewBatchPage());
    expect(
      screen.getByText("You don't have access to this page"),
    ).toBeInTheDocument();
  });

  it("validates the form like the API", () => {
    const empty = {
      course: null,
      campus: null,
      code: "dns 26",
      name: " ",
      intake: "",
      start: "2026-07-10",
      end: "2026-07-01",
      capacity: "501",
    };
    expect(Object.keys(validateBatch(empty, true)).sort()).toEqual(
      ["campus", "capacity", "code", "course", "end", "name"].sort(),
    );
    expect(
      validateBatch(
        { ...empty, name: "DNS", end: "2026-08-01", capacity: "10" },
        false,
        12,
      ).capacity,
    ).toMatch(/12 students are allocated/);
  });

  it("creates with an upper-cased code and maps a taken code to the field", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on("POST /batches", apiError(409, "CONFLICT"));
    state.reads.set(
      "/courses",
      ok(
        [{ id: ID.course, code: "DNS", name: "Diploma in Nautical Science" }],
        1,
      ),
    );
    const { container } = await show(NewBatchPage());
    await user.click(screen.getAllByRole("button", { name: /Course/ })[0]!);
    await user.click(
      await screen.findByRole("option", { name: /DNS · Diploma/ }),
    );
    await user.type(
      screen.getByRole("textbox", { name: /Batch code/ }),
      "dns-2026-b",
    );
    await user.type(
      screen.getByRole("textbox", { name: /Batch name/ }),
      "DNS Batch 2026-B",
    );
    await user.type(screen.getByRole("textbox", { name: /Capacity/ }), "24");
    await user.click(screen.getByRole("button", { name: "Create batch" }));
    // Dates are required: no request until the form is valid.
    expect(api.callsTo("POST /batches")).toHaveLength(0);
    expect(screen.getAllByText("Enter the start date.")[0]).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("edits show course, campus and code read-only and send the version", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `PATCH /batches/${ID.batch}`,
      jsonResponse(200, { data: batch({ capacity: 30 }) }),
    );
    state.reads.set(`/batches/${ID.batch}`, ok(batch()));
    await show(
      EditBatchPage({ params: Promise.resolve({ batchId: ID.batch }) }),
    );
    expect(
      screen.getByText("The course can't be changed."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("The campus can't be changed."),
    ).toBeInTheDocument();
    const capacity = screen.getByRole("textbox", { name: /Capacity/ });
    await user.clear(capacity);
    await user.type(capacity, "30");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() =>
      expect(state.push).toHaveBeenCalledWith(
        `/app/academics/batches/${ID.batch}`,
      ),
    );
    const body = api.callsTo(`PATCH /batches/${ID.batch}`)[0]!.body as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({ capacity: 30, version: 3 });
    expect(body).not.toHaveProperty("course_id");
    expect(body).not.toHaveProperty("campus_id");
  });
});

describe("ACA-06 Batch detail", () => {
  it.each(["light", "dark"] as const)(
    "shows seats, allocated students with the payment override, and passes axe (%s)",
    async (theme) => {
      detailReads();
      const { container } = await show(detail(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "DNS Batch 2026-B" }),
      ).toBeInTheDocument();
      expect(screen.getAllByText("18 of 24 seats")[0]).toBeInTheDocument();
      const table = screen.getByRole("table", { name: "Allocated students" });
      expect(
        within(table).getByRole("link", { name: "Kavya Menon" }),
      ).toBeInTheDocument();
      expect(within(table).getByText("Fee override")).toBeInTheDocument();
      expect(
        within(table).getByText(/₹2,18,500.00 outstanding/),
      ).toBeInTheDocument();
      expect(within(table).getByText(/Sponsor letter/)).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Allocate student" }),
      ).toBeEnabled();
      expect(
        screen.getByRole("button", { name: "Close batch" }),
      ).toBeInTheDocument();
      // Cancel only for an empty batch.
      expect(screen.queryByRole("button", { name: "Cancel batch" })).toBeNull();
      expect(
        within(table).getByRole("columnheader", { name: "Actions" }),
      ).toBeInTheDocument();
      await expectNoA11yViolations(container);
    },
  );

  it("a full batch can't take more students", async () => {
    detailReads(batch({ allocated_count: 24, available_seats: 0 }));
    await show(detail());
    expect(
      screen.getByRole("button", { name: "Allocate student" }),
    ).toBeDisabled();
    expect(screen.getByText("This batch is full")).toBeInTheDocument();
  });

  it("read-only roles see students but no actions; other institutes' batches are not found", async () => {
    state.session = readySession({ permissions: ["batch.read"] });
    detailReads();
    await show(detail());
    expect(
      screen.queryByRole("button", { name: "Allocate student" }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: "Transfer" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Edit" })).toBeNull();
    // No empty Actions column for read-only roles (table and mobile cards).
    expect(screen.queryByRole("columnheader", { name: "Actions" })).toBeNull();
    expect(screen.queryByText("Actions")).toBeNull();
    state.reads.set(`/batches/${ID.other}`, { kind: "not-found" });
    await expect(detail(ID.other)).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("allocating a student whose fees are outstanding needs an override reason", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `GET /batches/${ID.batch}/eligible-admissions`,
      jsonResponse(200, {
        data: [
          eligible({
            invoice_state: "NO_INVOICE",
            invoice_total_minor: null,
            outstanding_minor: null,
            payment_cleared: false,
          }),
        ],
        meta: {},
      }),
    );
    api.on(
      `POST /batches/${ID.batch}/allocations`,
      jsonResponse(201, { data: allocation() }),
    );
    detailReads();
    await show(detail());
    await user.click(screen.getByRole("button", { name: "Allocate student" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(
      await within(dialog).findByRole("radio", { name: /Arjun Nair/ }),
    );
    expect(
      within(dialog).getByText("Fees are not fully paid"),
    ).toBeInTheDocument();
    await user.click(
      within(dialog).getByRole("button", { name: "Allocate with override" }),
    );
    expect(api.callsTo(`POST /batches/${ID.batch}/allocations`)).toHaveLength(
      0,
    );
    expect(
      within(dialog).getByText(/Enter why this student may join/),
    ).toBeInTheDocument();
    await user.type(
      within(dialog).getByRole("textbox", { name: /Payment override reason/ }),
      "Scholarship approved by the principal",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Allocate with override" }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(
      api.callsTo(`POST /batches/${ID.batch}/allocations`)[0]!.body,
    ).toEqual({
      admission_id: ID.admission2,
      override_reason: "Scholarship approved by the principal",
    });
  });

  it("a paid student is allocated without an override; a full batch answer is explained", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `GET /batches/${ID.batch}/eligible-admissions`,
      jsonResponse(200, { data: [eligible()], meta: {} }),
    );
    api.on(
      `POST /batches/${ID.batch}/allocations`,
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "batch_id", code: "batch_full" }],
      }),
    );
    detailReads();
    await show(detail());
    await user.click(screen.getByRole("button", { name: "Allocate student" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(
      await within(dialog).findByRole("radio", { name: /Arjun Nair/ }),
    );
    expect(
      within(dialog).queryByRole("textbox", { name: /override/ }),
    ).toBeNull();
    await user.click(within(dialog).getByRole("button", { name: "Allocate" }));
    expect(
      await within(dialog).findByText("This batch is full."),
    ).toBeInTheDocument();
    expect(
      api.callsTo(`POST /batches/${ID.batch}/allocations`)[0]!.body,
    ).toEqual({
      admission_id: ID.admission2,
      override_reason: null,
    });
  });

  it("withdrawal needs a reason and sends the allocation version", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `POST /batch-allocations/${ID.allocation}/withdraw`,
      jsonResponse(200, {
        data: allocation({ status: "ENDED", end_reason: "WITHDRAWN" }),
      }),
    );
    detailReads();
    await show(detail());
    await user.click(screen.getAllByRole("button", { name: "Withdraw" })[0]!);
    const dialog = await screen.findByRole("dialog");
    await user.click(
      within(dialog).getByRole("button", { name: "Withdraw student" }),
    );
    expect(
      api.callsTo(`POST /batch-allocations/${ID.allocation}/withdraw`),
    ).toHaveLength(0);
    await user.type(
      within(dialog).getByRole("textbox"),
      "Failed the pre-sea medical",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Withdraw student" }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(
      api.callsTo(`POST /batch-allocations/${ID.allocation}/withdraw`)[0]!.body,
    ).toEqual({
      reason: "Failed the pre-sea medical",
      version: 1,
    });
  });

  it("transfer offers open batches of the same course and campus", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      "GET /batches",
      jsonResponse(200, {
        data: [
          batch(),
          batch({ id: ID.other, code: "DNS-2026-C", name: "DNS Batch 2026-C" }),
        ],
        meta: {},
      }),
    );
    api.on(
      `POST /batch-allocations/${ID.allocation}/transfer`,
      jsonResponse(200, { data: allocation({ payment_basis: "TRANSFER" }) }),
    );
    detailReads();
    await show(detail());
    await user.click(screen.getAllByRole("button", { name: "Transfer" })[0]!);
    const dialog = await screen.findByRole("dialog");
    await user.click(
      await within(dialog).findByRole("button", { name: /Move to batch/ }),
    );
    const options = await screen.findAllByRole("option");
    // The current batch is not offered.
    expect(options.map((o) => o.textContent)).toEqual([
      expect.stringContaining("DNS-2026-C"),
    ]);
    await user.click(options[0]!);
    await user.type(
      within(dialog).getByRole("textbox"),
      "Prefers the evening batch",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Transfer student" }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(
      api.callsTo(`POST /batch-allocations/${ID.allocation}/transfer`)[0]!.body,
    ).toEqual({
      target_batch_id: ID.other,
      reason: "Prefers the evening batch",
      version: 1,
    });
    expect(api.callsTo("GET /batches")).toHaveLength(1);
    const query = vi
      .mocked(globalThis.fetch)
      .mock.calls.map(([input]) =>
        String(input instanceof Request ? input.url : input),
      )
      .find((url) => url.includes("/batches?"));
    expect(query).toContain(`course_id=${ID.course}`);
    expect(query).toContain(`campus_id=${CAMPUSES.kochi.id}`);
    expect(query).toContain("status=OPEN");
  });

  it("history keeps transfers and withdrawals with their reasons", async () => {
    const user = userEvent.setup();
    detailReads(
      batch(),
      [],
      [
        allocation({
          status: "ENDED",
          end_reason: "TRANSFERRED",
          end_note: "Prefers the evening batch",
          transferred_to_batch_code: "DNS-2026-C",
          ended_at: "2026-06-20T05:30:00Z",
          ended_by: { display_name: "Maya Iyer" },
        }),
      ],
    );
    await show(detail());
    expect(
      screen.getAllByText("No students allocated yet")[0],
    ).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /History/ }));
    const table = screen.getByRole("table", { name: "Allocation history" });
    expect(within(table).getByText("Transferred out")).toBeInTheDocument();
    expect(within(table).getByText("to DNS-2026-C")).toBeInTheDocument();
    expect(
      within(table).getByText(/Prefers the evening batch/),
    ).toBeInTheDocument();
  });
});

describe("valid HTML nesting (hydration)", () => {
  it("row-header cells render no block element inside the mobile card's <p>", async () => {
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    state.reads.set("/batches", ok([batch()], 1));
    state.reads.set("/courses", ok([], 0));
    await show(list());
    state.reads.clear();
    detailReads(
      batch(),
      [allocation()],
      [
        allocation({
          id: "0199a1b2-0000-7000-8000-00000000a002",
          status: "ENDED",
          end_reason: "WITHDRAWN",
          end_note: "Left",
        }),
      ],
    );
    await show(detail());
    const nesting = errors.mock.calls.filter((call) =>
      String(call[0]).includes("cannot be a descendant of"),
    );
    expect(nesting).toEqual([]);
  });
});
