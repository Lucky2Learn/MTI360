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

// Dialog / Modal (DESIGN-SYSTEM.md §48; T00-07 D9: this is the generic modal
// container). React Aria: role="dialog", focus trapped inside, first focusable
// element (or an autoFocus control) receives focus, focus returns to the
// trigger on close, Escape closes, page scroll is locked. Centred on tablet and
// up; near-full-screen sheet with a 16px margin on mobile. Content scrolls
// inside the panel so the dialog never exceeds the viewport.

export type DialogSize = "sm" | "md" | "lg" | "xl";

const sizes: Record<DialogSize, string> = {
  sm: "tablet:max-w-sm",
  md: "tablet:max-w-lg",
  lg: "tablet:max-w-2xl",
  xl: "tablet:max-w-4xl",
};

export type DialogProps = PanelDialogProps & {
  size?: DialogSize;
  /** Element that opens the dialog (Button / IconButton). Omit for controlled use. */
  trigger?: ReactElement;
  isOpen?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (isOpen: boolean) => void;
  /** Close when clicking the scrim (default true). Escape always closes. */
  isDismissable?: boolean;
};

export function Dialog({
  size = "md",
  trigger,
  isOpen,
  defaultOpen,
  onOpenChange,
  isDismissable = true,
  ...panel
}: DialogProps) {
  const overlay = (
    <ModalOverlay
      isDismissable={isDismissable}
      {...(trigger ? {} : { isOpen, defaultOpen, onOpenChange })}
      className={cx(
        modalBackdrop,
        "z-(--z-modal) items-center justify-center p-4",
      )}
    >
      <Modal
        className={cx(
          panelSurface,
          "max-h-full w-full rounded-xl",
          sizes[size],
        )}
      >
        <PanelDialog {...panel} />
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
