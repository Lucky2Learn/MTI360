import { cx } from "@/design-system/lib/cx";

import { formatPaise } from "./money";

// An amount in rupees from integer paise (readiness plan §4): tabular
// numerals, so columns of amounts line up; right alignment is the caller's
// (table cells). Display only. Server-component compatible.

export function Amount({
  minor,
  strong = false,
}: {
  minor: number;
  strong?: boolean;
}) {
  return (
    <span
      className={cx("whitespace-nowrap tabular-nums", strong && "font-medium")}
    >
      {formatPaise(minor)}
    </span>
  );
}
