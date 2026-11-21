// Batch API wire types (Phase 02-6). Mirrors app/modules/batches/schemas.py.

export type BatchStatus = "OPEN" | "CLOSED" | "CANCELLED";
export type AllocationStatus = "ACTIVE" | "ENDED";
export type EndReason = "TRANSFERRED" | "WITHDRAWN";
export type PaymentBasis = "PAID" | "OVERRIDE" | "TRANSFER";
export type InvoiceState = "PAID" | "PARTIALLY_PAID" | "ISSUED" | "NO_INVOICE";

export type RefWire = { id: string; code: string; name: string };

/** `BatchOut`. */
export type BatchWire = {
  id: string;
  code: string;
  name: string;
  intake_label: string | null;
  course: RefWire;
  campus: RefWire;
  start_date: string;
  end_date: string;
  capacity: number;
  allocated_count: number;
  available_seats: number;
  status: BatchStatus;
  status_reason: string | null;
  created_at: string;
  updated_at: string;
  version: number;
};

export type StudentRefWire = { id: string; number: string; full_name: string };

/** `AllocationOut`. */
export type AllocationWire = {
  id: string;
  batch: RefWire;
  course: RefWire;
  campus_id: string;
  campus_name: string;
  admission_id: string;
  admission_number: string;
  student: StudentRefWire;
  status: AllocationStatus;
  payment_basis: PaymentBasis;
  payment_override: {
    reason: string;
    invoice_state: InvoiceState;
    outstanding_minor: number | null;
  } | null;
  transferred_from_id: string | null;
  transferred_from_batch_code: string | null;
  transferred_to_batch_code: string | null;
  allocated_at: string;
  allocated_by: { display_name: string } | null;
  end_reason: EndReason | null;
  end_note: string | null;
  ended_at: string | null;
  ended_by: { display_name: string } | null;
  version: number;
};

/** `EligibleAdmissionOut`: an admitted student who may join the batch. */
export type EligibleAdmissionWire = {
  admission_id: string;
  admission_number: string;
  approved_at: string;
  student: StudentRefWire;
  invoice_state: InvoiceState;
  invoice_total_minor: number | null;
  outstanding_minor: number | null;
  payment_cleared: boolean;
};

/** `BatchActivityOut`. */
export type BatchActivityWire = {
  id: string;
  kind: string;
  actor: { display_name: string } | null;
  details: Record<string, unknown>;
  created_at: string;
};
