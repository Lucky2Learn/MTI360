// Money for Finance-lite (Phase 02-5; ADR-0022 §6). Amounts are integer paise
// in INR. Typed input is converted to paise by string handling only — never
// through floating-point arithmetic — and the server computes every total.

/** ₹1,00,00,00,000.00 per line, invoice or payment (the API's limit). */
export const MAX_AMOUNT_MINOR = 100_000_000_000;

const PATTERN = /^(\d+)(?:\.(\d{0,2}))?$/;
// Indian grouping (1,25,000) or international grouping (125,000), or none.
const GROUPED_INDIAN = /^\d{1,2}(,\d{2})*,\d{3}$/;
const GROUPED_INTERNATIONAL = /^\d{1,3}(,\d{3})+$/;

/**
 * Paise for an amount typed in rupees ("1,25,000.50" → 12500050), or null when
 * it is not a valid, non-negative amount with at most two decimal places.
 * A leading "₹" and surrounding spaces are allowed; anything else is refused.
 */
export function parsePaise(input: string): number | null {
  const text = input.trim().replace(/^₹\s*/, "");
  if (!text) return null;
  const [whole = "", ...rest] = text.split(".");
  if (rest.length > 1) return null;
  if (whole.includes(",")) {
    if (!GROUPED_INDIAN.test(whole) && !GROUPED_INTERNATIONAL.test(whole)) {
      return null;
    }
  }
  const plain = `${whole.replaceAll(",", "")}${rest.length ? `.${rest[0]}` : ""}`;
  const match = PATTERN.exec(plain);
  if (!match) return null;
  const rupees = match[1]!.replace(/^0+(?=\d)/, "");
  const paise = (match[2] ?? "").padEnd(2, "0");
  if (rupees.length > 12) return null;
  const value = Number(`${rupees}${paise}`);
  return Number.isSafeInteger(value) && value <= MAX_AMOUNT_MINOR
    ? value
    : null;
}

const RUPEES = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** "₹1,25,000.50" for 12500050 paise. Display only. */
export function formatPaise(paise: number): string {
  const sign = paise < 0 ? "-" : "";
  const absolute = Math.abs(paise);
  const rupees = Math.trunc(absolute / 100);
  const remainder = absolute % 100;
  // Format the integer rupees, then append the exact paise (no float division).
  const formatted = RUPEES.format(rupees).replace(/\.\d{2}$/, "");
  return `${sign}${formatted}.${String(remainder).padStart(2, "0")}`;
}

/** The editable text of an amount: "125000.50" (no grouping, no symbol). */
export function paiseInput(paise: number): string {
  const rupees = Math.trunc(paise / 100);
  const remainder = paise % 100;
  return remainder === 0
    ? String(rupees)
    : `${rupees}.${String(remainder).padStart(2, "0")}`;
}
