import type {
  FeeStructureWire,
  FinanceSummaryWire,
  InvoiceDetailWire,
  InvoiceWire,
  PaymentWire,
} from "@/lib/api/finance";

import { IDS } from "./admissions-fixtures";

// Finance-lite fixtures for frontend tests (Phase 02-5; ADR-0022). Realistic
// maritime sample data (CLAUDE.md §61); amounts are integer paise in INR.
// Never used by application code.

export const FIN = {
  structure: "0199a1b2-0000-7000-8000-000000000f01",
  draftStructure: "0199a1b2-0000-7000-8000-000000000f02",
  invoice: "0199a1b2-0000-7000-8000-000000000f11",
  otherInvoice: "0199a1b2-0000-7000-8000-000000000f12",
  admission: "0199a1b2-0000-7000-8000-000000000f21",
  cash: "0199a1b2-0000-7000-8000-000000000f31",
  cheque: "0199a1b2-0000-7000-8000-000000000f32",
  receipt: "0199a1b2-0000-7000-8000-000000000f41",
  activity: "0199a1b2-0000-7000-8000-000000000f51",
} as const;

export const KOCHI_CAMPUS = {
  id: "a3f1c2d4-5b6e-4f70-8a9b-0c1d2e3f4a11",
  code: "KOC",
};

const GPR = { id: IDS.gpr, code: "GPR", name: "General Purpose Rating" };
const ARJUN = {
  id: IDS.student,
  number: "STU-2026-00007",
  full_name: "Arjun Nair",
};

export const FINANCE_MANAGER = [
  "fee_structure.read",
  "fee_structure.manage",
  "invoice.read",
  "invoice.issue",
  "invoice.cancel",
  "payment.record",
  "payment.reverse",
  "student.read",
  "course.read",
];

export const FINANCE_OFFICER = [
  "fee_structure.read",
  "invoice.read",
  "invoice.issue",
  "payment.record",
  "student.read",
  "course.read",
];

export function feeStructure(
  overrides: Partial<FeeStructureWire> = {},
): FeeStructureWire {
  return {
    id: FIN.structure,
    course: GPR,
    name: "GPR fees 2026-27",
    status: "ACTIVE",
    items: [
      { fee_head: "Tuition", amount_minor: 18_500_000 },
      { fee_head: "Hostel", amount_minor: 6_000_000 },
      { fee_head: "Uniform", amount_minor: 850_000 },
    ],
    total_minor: 25_350_000,
    currency: "INR",
    activated_at: "2026-09-01T05:30:00Z",
    archived_at: null,
    created_at: "2026-08-20T05:30:00Z",
    updated_at: "2026-09-01T05:30:00Z",
    version: 2,
    ...overrides,
  };
}

export function invoice(overrides: Partial<InvoiceWire> = {}): InvoiceWire {
  return {
    id: FIN.invoice,
    number: "INV-FY2026-27-00012",
    status: "PARTIALLY_PAID",
    admission: { id: FIN.admission, number: "ADM-2026-00007" },
    student: ARJUN,
    course: GPR,
    campus: KOCHI_CAMPUS,
    total_minor: 25_350_000,
    paid_minor: 10_000_000,
    balance_minor: 15_350_000,
    currency: "INR",
    due_date: "2026-10-31",
    overdue: false,
    adjusted: false,
    issued_at: "2026-10-05T06:00:00Z",
    version: 3,
    ...overrides,
  };
}

export function payment(overrides: Partial<PaymentWire> = {}): PaymentWire {
  return {
    id: FIN.cash,
    invoice: { id: FIN.invoice, number: "INV-FY2026-27-00012" },
    student: ARJUN,
    amount_minor: 10_000_000,
    currency: "INR",
    method: "CASH",
    reference: null,
    received_on: "2026-10-06",
    status: "CONFIRMED",
    status_reason: null,
    recorded_by: "Kavita Menon",
    recorded_by_me: false,
    recorded_at: "2026-10-06T06:30:00Z",
    confirmed_at: "2026-10-06T06:30:00Z",
    closed_at: null,
    receipt: {
      id: FIN.receipt,
      number: "RCT-FY2026-27-00031",
      issued_at: "2026-10-06T06:30:00Z",
      cancelled: false,
    },
    version: 1,
    ...overrides,
  };
}

export function pendingCheque(
  overrides: Partial<PaymentWire> = {},
): PaymentWire {
  return payment({
    id: FIN.cheque,
    amount_minor: 5_000_000,
    method: "CHEQUE",
    reference: "Cheque 004512, State Bank of India",
    received_on: "2026-10-08",
    status: "PENDING",
    confirmed_at: null,
    receipt: null,
    ...overrides,
  });
}

export function invoiceDetail(
  overrides: Partial<InvoiceDetailWire> = {},
): InvoiceDetailWire {
  return {
    ...invoice(),
    fee_structure: { id: FIN.structure, name: "GPR fees 2026-27", version: 2 },
    structure_total_minor: 25_350_000,
    adjustment_reason: null,
    status_reason: null,
    cancelled_at: null,
    pending_minor: 0,
    lines: [
      {
        position: 1,
        fee_head: "Tuition",
        amount_minor: 18_500_000,
        structure_amount_minor: 18_500_000,
        adjusted: false,
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
    payments: [payment()],
    activity: [
      {
        id: FIN.activity,
        kind: "ISSUED",
        actor: "Kavita Menon",
        details: { number: "INV-FY2026-27-00012" },
        created_at: "2026-10-05T06:00:00Z",
      },
    ],
    ...overrides,
  };
}

export function summary(
  overrides: Partial<FinanceSummaryWire> = {},
): FinanceSummaryWire {
  return {
    invoice_count: 8,
    invoiced_minor: 180_000_000,
    collected_minor: 95_000_000,
    outstanding_minor: 85_000_000,
    outstanding_count: 5,
    overdue_minor: 30_000_000,
    overdue_count: 2,
    pending_minor: 5_000_000,
    pending_count: 1,
    currency: "INR",
    as_of: "2026-10-11",
    ...overrides,
  };
}
