"use client";

import {
  Dialog as AriaDialog,
  DialogTrigger,
  Heading,
  Popover as AriaPopover,
  type PopoverProps as AriaPopoverProps,
} from "react-aria-components";

import { popoverSurface } from "@/design-system/components/Overlay/overlay";
import { cx } from "@/design-system/lib/cx";

import type { ReactElement, ReactNode } from "react";

// Popover (T00-07C): anchored, non-modal-looking panel for supplementary
// content and small interactive groups (help, quick settings, filter details).
// React Aria: anchored to the trigger, flips/shifts to stay in the viewport,
// Escape and outside interaction close it, focus moves into the panel and
// returns to the trigger. The panel is a labelled dialog. Select, Combobox and
// DatePicker (07B) share the same surface (Overlay/overlay.ts) but keep their
// own React Aria popovers because their collections need them.

export type PopoverSize = "sm" | "md";

const sizes: Record<PopoverSize, string> = {
  sm: "w-64",
  md: "w-80",
};

export type PopoverProps = {
  /** Pressable element that opens the popover (Button / IconButton). */
  trigger: ReactElement;
  /** Visible heading; if omitted, provide `aria-label`. */
  title?: string;
  "aria-label"?: string;
  children: ReactNode;
  placement?: AriaPopoverProps["placement"];
  size?: PopoverSize;
  isOpen?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (isOpen: boolean) => void;
};

export function Popover({
  trigger,
  title,
  "aria-label": ariaLabel,
  children,
  placement = "bottom start",
  size = "md",
  isOpen,
  defaultOpen,
  onOpenChange,
}: PopoverProps) {
  return (
    <DialogTrigger
      isOpen={isOpen}
      defaultOpen={defaultOpen}
      onOpenChange={onOpenChange}
    >
      {trigger}
      <AriaPopover
        placement={placement}
        offset={8}
        containerPadding={16}
        className={cx(popoverSurface, "max-w-full", sizes[size])}
      >
        <AriaDialog
          aria-label={title ? undefined : ariaLabel}
          className="flex flex-col gap-2 p-4 outline-none"
        >
          {title && (
            <Heading
              slot="title"
              className="text-body-sm font-semibold text-text-primary"
            >
              {title}
            </Heading>
          )}
          <div className="text-body-sm text-text-secondary">{children}</div>
        </AriaDialog>
      </AriaPopover>
    </DialogTrigger>
  );
}
