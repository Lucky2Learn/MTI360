"use client";

import { DialogTrigger, Modal, ModalOverlay } from "react-aria-components";

import {
  modalBackdrop,
  panelSurface,
} from "@/design-system/components/Overlay/overlay";
import {
  PanelDialog,
  type PanelDialogProps,
} from "@/design-system/components/Overlay/PanelDialog";
import { cx } from "@/design-system/lib/cx";

import type { ReactElement } from "react";

// Drawer (DESIGN-SYSTEM.md §47, §74): modal side/top/bottom panel for mobile
// filters, mobile navigation (T00-08), contextual and detail panels. React
// Aria modal: focus trapped and restored, Escape closes, scrim click closes
// (optional), page scroll locked. Left/right drawers are full width on mobile
// and a fixed token width from tablet; top/bottom sheets span the width and
// leave 64px of the page visible. Slide-in uses @starting-style and is removed
// under reduced motion.

export type DrawerSide = "left" | "right" | "top" | "bottom";
export type DrawerSize = "sm" | "md" | "lg";

const overlayPlacement: Record<DrawerSide, string> = {
  left: "justify-start",
  right: "justify-end",
  top: "flex-col justify-start pb-16",
  bottom: "flex-col justify-end pt-16",
};

const widths: Record<DrawerSize, string> = {
  sm: "tablet:max-w-sm",
  md: "tablet:max-w-md",
  lg: "tablet:max-w-lg",
};

const panelPlacement: Record<DrawerSide, string> = {
  left: "h-full w-full border-y-0 border-l-0 starting:-translate-x-full",
  right: "h-full w-full border-y-0 border-r-0 starting:translate-x-full",
  top: "max-h-full w-full rounded-b-xl border-x-0 border-t-0 starting:-translate-y-full",
  bottom:
    "max-h-full w-full rounded-t-xl border-x-0 border-b-0 starting:translate-y-full",
};

export type DrawerProps = PanelDialogProps & {
  side?: DrawerSide;
  /** Width for left/right drawers from the tablet breakpoint. */
  size?: DrawerSize;
  trigger?: ReactElement;
  isOpen?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (isOpen: boolean) => void;
  isDismissable?: boolean;
};

export function Drawer({
  side = "right",
  size = "md",
  trigger,
  isOpen,
  defaultOpen,
  onOpenChange,
  isDismissable = true,
  closeLabel = "Close panel",
  ...panel
}: DrawerProps) {
  const horizontal = side === "left" || side === "right";
  const overlay = (
    <ModalOverlay
      isDismissable={isDismissable}
      {...(trigger ? {} : { isOpen, defaultOpen, onOpenChange })}
      className={cx(modalBackdrop, "z-(--z-drawer)", overlayPlacement[side])}
    >
      <Modal
        className={cx(
          panelSurface,
          "transition-transform motion-reduce:transition-none",
          panelPlacement[side],
          horizontal && widths[size],
        )}
      >
        <PanelDialog closeLabel={closeLabel} {...panel} />
      </Modal>
    </ModalOverlay>
  );

  if (!trigger) return overlay;

  return (
    <DialogTrigger
      isOpen={isOpen}
      defaultOpen={defaultOpen}
      onOpenChange={onOpenChange}
    >
      {trigger}
      {overlay}
    </DialogTrigger>
  );
}
