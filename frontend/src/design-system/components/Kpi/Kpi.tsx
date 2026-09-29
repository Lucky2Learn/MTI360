import { useId, type ReactNode } from "react";

import {
  TrendDownIcon,
  TrendFlatIcon,
  TrendUpIcon,
  type IconComponent,
} from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

// KPI (DESIGN-SYSTEM.md §51): Label · Value · Trend · Comparison · Context.
//
//   Active Students
//   1,284
//   ↑ 8.4%  vs last month
//
// The trend is communicated by an arrow icon, a sign and screen-reader text
// ("Increased by 8.4%") — never by colour alone. Whether "up" is good depends
// on the metric, so `sentiment` is set by the caller (e.g. overdue fees up =
// negative). Values are pre-formatted by the caller (locale/currency, D10).
// A value wider than the card (e.g. "₹12,40,00,000" in a narrow column)
// wraps instead of spilling out (T00-09); prefer compact formats such as
// "₹12.4 Cr" for multi-column KPI rows. Server-component compatible.

export type KpiTrendDirection = "up" | "down" | "flat";
export type KpiSentiment = "positive" | "negative" | "neutral";

export type KpiTrend = {
  direction: KpiTrendDirection;
  /** Formatted change, e.g. "8.4%" or "₹1.2L". */
  value: string;
  sentiment?: KpiSentiment;
};

export type KpiProps = {
  label: string;
  /** Formatted value, e.g. "1,284" or "₹12,40,000". */
  value: string;
  trend?: KpiTrend;
  /** Comparison basis, e.g. "vs last month". */
  comparison?: string;
  /** Supporting context below the value. */
  context?: ReactNode;
  icon?: IconComponent;
};

const trendIcon: Record<KpiTrendDirection, IconComponent> = {
  up: TrendUpIcon,
  down: TrendDownIcon,
  flat: TrendFlatIcon,
};

const trendWord: Record<KpiTrendDirection, string> = {
  up: "Increased by",
  down: "Decreased by",
  flat: "No change",
};

const sentimentText: Record<KpiSentiment, string> = {
  positive: "text-success-text",
  negative: "text-error-text",
  neutral: "text-text-secondary",
};

export function Kpi({
  label,
  value,
  trend,
  comparison,
  context,
  icon: Icon,
}: KpiProps) {
  const labelId = useId();
  const TrendIcon = trend ? trendIcon[trend.direction] : null;

  return (
    <div
      role="group"
      aria-labelledby={labelId}
      className="flex flex-col gap-2 rounded-xl border border-border-subtle bg-surface-primary p-4 text-text-primary shadow-sm tablet:p-6"
    >
      <div className="flex items-center justify-between gap-2">
        <p
          id={labelId}
          className="text-body-sm font-medium text-text-secondary"
        >
          {label}
        </p>
        {Icon && (
          <Icon
            aria-hidden="true"
            className="size-5 shrink-0 text-accent-maritime"
          />
        )}
      </div>
      <p className="text-page-title wrap-anywhere text-text-primary tabular-nums">
        {value}
      </p>
      {(trend || comparison) && (
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-body-sm">
          {trend && TrendIcon && (
            <span
              className={cx(
                "inline-flex items-center gap-1 font-semibold tabular-nums",
                sentimentText[trend.sentiment ?? "neutral"],
              )}
            >
              <TrendIcon aria-hidden="true" className="size-4" />
              <span className="sr-only">
                {trend.direction === "flat"
                  ? `${trendWord.flat} (${trend.value})`
                  : `${trendWord[trend.direction]} ${trend.value}`}
              </span>
              <span aria-hidden="true">
                {trend.direction === "up"
                  ? "+"
                  : trend.direction === "down"
                    ? "−"
                    : "±"}
                {trend.value}
              </span>
            </span>
          )}
          {comparison && <span className="text-text-muted">{comparison}</span>}
        </p>
      )}
      {context && (
        <div className="text-body-sm text-text-secondary">{context}</div>
      )}
    </div>
  );
}
