import { toneIcon, toneSurface } from "@/design-system/components/tone";
import { cx } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// Alert (DESIGN-SYSTEM.md §49): inline, concise, actionable message.
// Tone = icon shape + title/text + colour (never colour alone). Errors use
// role="alert" (assertive); other tones use role="status" (polite), so a
// dynamically inserted alert is announced appropriately. Server-component
// compatible; pass interactive actions (e.g. a Button) through `action`.

export type AlertTone = "info" | "success" | "warning" | "error";

export type AlertProps = {
  tone?: AlertTone;
  title: string;
  children?: ReactNode;
  /** Optional follow-up action, e.g. <Button variant="tertiary">View invoice</Button>. */
  action?: ReactNode;
};

export function Alert({ tone = "info", title, children, action }: AlertProps) {
  const Icon = toneIcon[tone]!;
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cx(
        "flex flex-col gap-3 rounded-lg border border-l-4 p-4 tablet:flex-row tablet:items-start",
        toneSurface[tone],
      )}
    >
      <div className="flex min-w-0 flex-1 gap-3">
        <Icon aria-hidden="true" className="size-5 shrink-0" />
        <div className="flex min-w-0 flex-col gap-1">
          <p className="text-body-sm font-semibold">{title}</p>
          {children && <div className="text-body-sm">{children}</div>}
        </div>
      </div>
      {action && (
        <div className="flex shrink-0 items-center pl-8 tablet:pl-0">
          {action}
        </div>
      )}
    </div>
  );
}
