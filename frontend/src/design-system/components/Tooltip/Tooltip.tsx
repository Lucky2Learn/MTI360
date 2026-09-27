"use client";

import {
  Tooltip as AriaTooltip,
  TooltipTrigger,
  type TooltipProps as AriaTooltipProps,
} from "react-aria-components";

import { cx } from "@/design-system/lib/cx";

import type { ReactElement } from "react";

// Tooltip (T00-07C): a short visible label for icon-only and compact
// controls, or the full text of a truncated label. React Aria: shows on hover
// after a delay and immediately on keyboard focus, hides on Escape / blur /
// pointer leave, repositions to stay in the viewport, linked to the trigger
// with aria-describedby. Never put essential information only in a tooltip —
// the trigger must already have an accessible name (e.g. IconButton `label`).
// High-contrast inverse surface: brand-primary with text-inverse (≥ 4.5:1).

export type TooltipProps = {
  /** Concise text (a few words). */
  content: string;
  /** The focusable trigger (Button / IconButton / other React Aria pressable). */
  children: ReactElement;
  placement?: AriaTooltipProps["placement"];
  /** Hover delay in ms (default 600). Keyboard focus shows immediately. */
  delay?: number;
  isDisabled?: boolean;
};

export function Tooltip({
  content,
  children,
  placement = "top",
  delay = 600,
  isDisabled = false,
}: TooltipProps) {
  return (
    <TooltipTrigger delay={delay} closeDelay={200} isDisabled={isDisabled}>
      {children}
      <AriaTooltip
        placement={placement}
        offset={6}
        containerPadding={16}
        className={cx(
          "z-(--z-toast) max-w-64 rounded-sm bg-brand-primary px-2 py-1 text-caption font-medium text-text-inverse shadow-md",
          "transition-opacity starting:opacity-0 motion-reduce:transition-none",
        )}
      >
        {content}
      </AriaTooltip>
    </TooltipTrigger>
  );
}
