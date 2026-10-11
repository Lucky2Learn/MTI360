import type { Tone } from "@/design-system/components";
import type {
  FeeStructureStatus,
  FinanceActivityKind,
  InvoiceStatus,
  PaymentMethod,
  PaymentStatus,
} from "@/lib/api/finance";

// Finance-lite copy (Phase 02-5; ADR-0022; readiness plan §4). Display only:
// permissions here gate controls for UX; the API decides.

export const FINANCE_PATH = "/app/finance";
export const STRUCTURES_PATH = `${FINANCE_PATH}/fee-structure`;
export const INVOICES_PATH = `${FINANCE_PATH}/invoices`;
export const PAYMENTS_PATH = `${FINANCE_PATH}/payments`;
export const OUTSTANDING_PATH = `${FINANCE_PATH}/outstanding`;

export const FEE_STRUCTURE_READ = "fee_structure.read";
export const FEE_STRUCTURE_MANAGE = "fee_structure.manage";
export const INVOICE_READ = "invoice.read";
export const INVOICE_ISSUE = "invoice.issue";
export const INVOICE_CANCEL = "invoice.cancel";
export const PAYMENT_RECORD = "payment.record";
export const PAYMENT_REVERSE = "payment.reverse";

/** Printed on every fee invoice view and print (ADR-0022 §2). */
export const NON_TAX_LABEL = "Fee invoice — not a tax invoice";

export const structurePath = (id: string) => `${STRUCTURES_PATH}/${id}`;
export const invoicePath = (id: string) => `${INVOICES_PATH}/${id}`;
export const paymentPath = (id: string) => `${PAYMENTS_PATH}/${id}`;
export const receiptPath = (id: string) => `${PAYMENTS_PATH}/${id}/receipt`;
export const issuePath = (studentId: string, admissionId: string) =>
  `${INVOICES_PATH}/new?student=${studentId}&admission=${admissionId}`;

export const STRUCTURE_STATUS_LABEL: Record<FeeStructureStatus, string> = {
  DRAFT: "Draft",
  ACTIVE: "Active",
  ARCHIVED: "Archived",
};

export const STRUCTURE_STATUS_TONE: Record<FeeStructureStatus, Tone> = {
  DRAFT: "neutral",
  ACTIVE: "success",
  ARCHIVED: "warning",
};

export const INVOICE_STATUS_LABEL: Record<InvoiceStatus, string> = {
  ISSUED: "Unpaid",
  PARTIALLY_PAID: "Partly paid",
  PAID: "Paid",
  CANCELLED: "Cancelled",
};

export const INVOICE_STATUS_TONE: Record<InvoiceStatus, Tone> = {
  ISSUED: "info",
  PARTIALLY_PAID: "warning",
  PAID: "success",
  CANCELLED: "neutral",
};

export const PAYMENT_STATUS_LABEL: Record<PaymentStatus, string> = {
  PENDING: "Awaiting clearance",
  CONFIRMED: "Confirmed",
  FAILED: "Failed",
  REVERSED: "Reversed",
};

export const PAYMENT_STATUS_TONE: Record<PaymentStatus, Tone> = {
  PENDING: "warning",
  CONFIRMED: "success",
  FAILED: "error",
  REVERSED: "neutral",
};

export const METHOD_LABEL: Record<PaymentMethod, string> = {
  CASH: "Cash",
  UPI: "UPI",
  BANK_TRANSFER: "Bank transfer",
  CHEQUE: "Cheque",
  DEMAND_DRAFT: "Demand draft",
};

/** Methods that wait for clearance (ADR-0022 §4). */
export const CLEARANCE_METHODS: ReadonlySet<PaymentMethod> = new Set([
  "CHEQUE",
  "DEMAND_DRAFT",
]);

export const REFERENCE_LABEL: Record<PaymentMethod, string> = {
  CASH: "Reference (optional)",
  UPI: "UPI transaction ID",
  BANK_TRANSFER: "UTR or bank reference",
  CHEQUE: "Cheque number and bank",
  DEMAND_DRAFT: "Demand draft number and bank",
};

export const ACTIVITY_LABEL: Record<FinanceActivityKind, string> = {
  ISSUED: "Fee invoice issued",
  CANCELLED: "Fee invoice cancelled",
  PAYMENT_RECORDED: "Payment recorded",
  PAYMENT_CONFIRMED: "Payment confirmed after clearance",
  PAYMENT_FAILED: "Payment failed",
  PAYMENT_REVERSED: "Payment reversed",
};
