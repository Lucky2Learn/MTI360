import {
  toneIcon,
  toneSurface,
  type Tone,
} from "@/design-system/components/tone";
import type { IconComponent } from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// Badge (DESIGN-SYSTEM.md §50): compact status or tag. Status is shown by text
// + icon + colour — never colour alone. Pill radius (§34). Server-component
// compatible.

export type BadgeTone = Tone;

export type BadgeProps = {
  /** Visible text, e.g. "Active", "Pending", "Overdue". Always required. */
  children: ReactNode;
  tone?: BadgeTone;
  /** Override the tone icon; `false` hides it (neutral tags). */
  icon?: IconComponent | false;
};

export function Badge({ children, tone = "neutral", icon }: BadgeProps) {
  const Icon = icon === false ? null : (icon ?? toneIcon[tone]);
  return (
    <span
      className={cx(
        "inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-1 text-caption-sm font-semibold",
        toneSurface[tone],
      )}
    >
      {Icon && <Icon aria-hidden="true" className="size-4 shrink-0" />}
      <span className="truncate">{children}</span>
    </span>
  );
}
