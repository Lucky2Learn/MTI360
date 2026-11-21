import { cx } from "@/design-system/lib/cx";

import { seats } from "./labels";

// Seat utilisation (Phase 02-6): "18 of 24 seats" with a meter. The text
// carries the information (never colour alone); the bar is a role="meter"
// with its value for assistive technology. Full batches use the warning
// token. Server-component compatible.

export function SeatMeter({
  capacity,
  allocated,
  compact = false,
}: {
  capacity: number;
  allocated: number;
  compact?: boolean;
}) {
  const { label, percent } = seats({ capacity, allocated_count: allocated });
  const full = allocated >= capacity;
  return (
    <div
      className={cx("flex min-w-0 flex-col gap-1", compact ? "w-32" : "w-full")}
    >
      <span
        className={cx(
          "text-body-sm text-text-primary tabular-nums",
          // One line in a table cell; free to wrap in a narrow summary column.
          compact && "whitespace-nowrap",
        )}
      >
        {label}
        {full ? " · Full" : ""}
      </span>
      <div
        role="meter"
        aria-label="Seats allocated"
        aria-valuemin={0}
        aria-valuemax={capacity}
        aria-valuenow={allocated}
        aria-valuetext={`${label}${full ? ", full" : ""}`}
        className="h-1.5 w-full overflow-hidden rounded-full bg-surface-secondary"
      >
        <div
          className={cx(
            "h-full rounded-full",
            full ? "bg-warning" : "bg-accent-maritime",
          )}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
