// Hand-typed contracts of the Finance-lite API (Phase 02-5; ADR-0022,
// addendum R1-R3). They mirror backend/app/modules/finance (schemas.py,
// invoice_schemas.py) field for field and contain only what the UI reads.
// Amounts are integer paise (`*_minor`) in INR; the server computes every
// total and balance. Fee invoices are non-tax (ADR-0022 §2).

export type FeeStructureStatus = "DRAFT" | "ACTIVE" | "ARCHIVED";
export type InvoiceStatus = "ISSUED" | "PARTIALLY_PAID" | "PAID" | "CANCELLED";
export type PaymentMethod =
  "CASH" | "UPI" | "BANK_TRANSFER" | "CHEQUE" | "DEMAND_DRAFT";
export type PaymentStatus = "PENDING" | "CONFIRMED" | "FAILED" | "REVERSED";
export type FinanceActivityKind =
  | "ISSUED"
  | "CANCELLED"
  | "PAYMENT_RECORDED"
  | "PAYMENT_CONFIRMED"
  | "PAYMENT_FAILED"
  | "PAYMENT_REVERSED";

export type FeeItemWire = { fee_head: string; amount_minor: number };

export type CourseRefWire = { id: string; code: string; name: string };

/** `FeeStructureOut`. */
export type FeeStructureWire = {
  id: string;
  course: CourseRefWire;
  name: string;
  status: FeeStructureStatus;
  items: FeeItemWire[];
  total_minor: number;
  currency: "INR";
  activated_at: string | null;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
  version: number;
};

export type NumberRefWire = { id: string; number: string };
export type StudentRefWire = { id: string; number: string; full_name: string };

/** `InvoiceOut`: a fee invoice in a list. */
export type InvoiceWire = {
  id: string;
  number: string;
  status: InvoiceStatus;
  admission: NumberRefWire;
  student: StudentRefWire;
  course: CourseRefWire;
  campus: { id: string; code: string };
  total_minor: number;
  paid_minor: number;
  balance_minor: number;
  currency: "INR";
  due_date: string;
  overdue: boolean;
  adjusted: boolean;
  issued_at: string;
  version: number;
};

export type InvoiceLineWire = {
  position: number;
  fee_head: string;
  amount_minor: number;
  /** The fee structure's amount; null for a line added at issue. */
  structure_amount_minor: number | null;
  adjusted: boolean;
};

export type ReceiptWire = {
  id: string;
  number: string;
  issued_at: string;
  /** The payment was reversed: the receipt stays, shown as cancelled. */
  cancelled: boolean;
};

/** `PaymentOut`. */
export type PaymentWire = {
  id: string;
  invoice: NumberRefWire;
  student: StudentRefWire;
  amount_minor: number;
  currency: "INR";
  method: PaymentMethod;
  reference: string | null;
  received_on: string;
  status: PaymentStatus;
  status_reason: string | null;
  recorded_by: string | null;
  /** The caller recorded it, so the server refuses their reversal (R1). UX only. */
  recorded_by_me: boolean;
  recorded_at: string;
  confirmed_at: string | null;
  closed_at: string | null;
  receipt: ReceiptWire | null;
  version: number;
};

export type FinanceActivityWire = {
  id: string;
  kind: FinanceActivityKind;
  actor: string | null;
  details: Record<string, unknown>;
  created_at: string;
};

/** `InvoiceDetailOut`. */
export type InvoiceDetailWire = InvoiceWire & {
  fee_structure: { id: string; name: string; version: number };
  structure_total_minor: number;
  adjustment_reason: string | null;
  status_reason: string | null;
  cancelled_at: string | null;
  pending_minor: number;
  lines: InvoiceLineWire[];
  payments: PaymentWire[];
  activity: FinanceActivityWire[];
};

/** `SummaryOut`: the live fee invoices the caller may see. */
export type FinanceSummaryWire = {
  invoice_count: number;
  invoiced_minor: number;
  collected_minor: number;
  outstanding_minor: number;
  outstanding_count: number;
  overdue_minor: number;
  overdue_count: number;
  pending_minor: number;
  pending_count: number;
  currency: "INR";
  /** Today's date in India Standard Time. */
  as_of: string;
};
