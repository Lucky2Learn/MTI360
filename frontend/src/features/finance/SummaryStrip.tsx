import { Kpi } from "@/design-system/components";
import { Grid } from "@/design-system/layout";
import type { FinanceSummaryWire } from "@/lib/api/finance";

import { formatDate } from "../shared/format";

import { formatPaise } from "./money";

// FIN-08 summary strip (Phase 02-5; readiness plan §2, §4): the server's
// totals over the live fee invoices the caller may see — nothing is computed
// here, and there are no trends (master readiness §21: no invented
// numbers). Exact rupees; a KPI wraps a long value instead of overflowing.
// Server-component compatible.

const count = (n: number, noun: string) =>
  `${n} ${n === 1 ? noun : `${noun}s`}`;

export function SummaryStrip({ summary }: { summary: FinanceSummaryWire }) {
  return (
    <section aria-labelledby="finance-summary" className="flex flex-col gap-3">
      <h2 id="finance-summary" className="sr-only">
        Summary
      </h2>
      <Grid columns={{ base: 1, tablet: 2, desktop: 4 }} gap="md">
        <Kpi
          label="Outstanding"
          value={formatPaise(summary.outstanding_minor)}
          context={count(summary.outstanding_count, "fee invoice")}
        />
        <Kpi
          label="Overdue"
          value={formatPaise(summary.overdue_minor)}
          context={count(summary.overdue_count, "fee invoice")}
        />
        <Kpi
          label="Awaiting clearance"
          value={formatPaise(summary.pending_minor)}
          context={`${count(summary.pending_count, "cheque or demand draft")} not yet in the balance`}
        />
        <Kpi
          label="Collected"
          value={formatPaise(summary.collected_minor)}
          context={`of ${formatPaise(summary.invoiced_minor)} invoiced`}
        />
      </Grid>
      <p className="text-caption text-text-secondary">
        {`Live fee invoices at your campuses, as of ${formatDate(summary.as_of)} (India Standard Time).`}
      </p>
    </section>
  );
}
