import {
  toneIcon,
  toneIndicator,
  toneLabel,
  type Tone,
} from "@/design-system/components/tone";
import { TimelineDotIcon, type IconComponent } from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// Timeline (DESIGN-SYSTEM.md §69): an ordered list of events — the base for
// activity feeds and, later, AuditTimeline. Semantic <ol>/<li> with <time>.
// Each event's status is carried by an icon shape and visually hidden text,
// never by colour alone. Order is the caller's (newest first or oldest first).
// Server-component compatible.

export type TimelineItem = {
  id: string;
  title: ReactNode;
  /** Machine-readable timestamp (ISO 8601) for <time dateTime>. */
  timestamp: string;
  /** Human-readable, pre-formatted time, e.g. "12 Oct 2026, 10:42". */
  timestampLabel: string;
  actor?: string;
  description?: ReactNode;
  tone?: Tone;
  icon?: IconComponent;
};

export type TimelineProps = {
  items: TimelineItem[];
  "aria-label": string;
};

export function Timeline({ items, "aria-label": ariaLabel }: TimelineProps) {
  return (
    <ol aria-label={ariaLabel} className="flex flex-col">
      {items.map((item, index) => {
        const tone = item.tone ?? "neutral";
        const Icon = item.icon ?? toneIcon[tone] ?? TimelineDotIcon;
        const isLast = index === items.length - 1;
        return (
          <li key={item.id} className="relative flex gap-3 pb-6 last:pb-0">
            {!isLast && (
              <span
                aria-hidden="true"
                className="absolute top-8 bottom-0 left-4 border-l border-border-default"
              />
            )}
            <span
              aria-hidden="true"
              className={cx(
                "relative flex size-8 shrink-0 items-center justify-center rounded-full border border-border-default bg-surface-primary",
                toneIndicator[tone],
              )}
            >
              <Icon className="size-4" />
            </span>
            <div className="flex min-w-0 flex-col gap-1 pt-1">
              <p className="text-body-sm font-semibold text-text-primary">
                {tone !== "neutral" && (
                  <span className="sr-only">{toneLabel[tone]}: </span>
                )}
                {item.title}
              </p>
              <p className="flex flex-wrap gap-x-2 text-caption text-text-muted">
                {item.actor && <span>{item.actor}</span>}
                <time dateTime={item.timestamp}>{item.timestampLabel}</time>
              </p>
              {item.description && (
                <div className="text-body-sm text-text-secondary">
                  {item.description}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
