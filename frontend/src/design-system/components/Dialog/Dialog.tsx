"use client";

import { useId, type ReactElement, type ReactNode } from "react";
import {
  Dialog as AriaDialog,
  DialogTrigger,
  Heading,
  Modal,
  ModalOverlay,
} from "react-aria-components";

import { IconButton } from "@/design-system/components/IconButton";
import {
  modalBackdrop,
  panelSurface,
} from "@/design-system/components/Overlay/overlay";
import { CloseIcon } from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

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

type Close = () => void;

export type DialogProps = {
  title: string;
  description?: ReactNode;
  /** Body content; a function receives `close`. */
  children?: ReactNode | ((close: Close) => ReactNode);
  /** Footer actions; a function receives `close`. */
  actions?: ReactNode | ((close: Close) => ReactNode);
  size?: DialogSize;
  /** Element that opens the dialog (Button / IconButton). Omit for controlled use. */
  trigger?: ReactElement;
  isOpen?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (isOpen: boolean) => void;
  /** Close when clicking the scrim (default true). Escape always closes. */
  isDismissable?: boolean;
  /** Show the × close button (default true). */
  showCloseButton?: boolean;
  closeLabel?: string;
  /** Internal: alertdialog semantics (AlertDialog). */
  role?: "dialog" | "alertdialog";
};

export function Dialog({
  title,
  description,
  children,
  actions,
  size = "md",
  trigger,
  isOpen,
  defaultOpen,
  onOpenChange,
  isDismissable = true,
  showCloseButton = true,
  closeLabel = "Close dialog",
  role = "dialog",
}: DialogProps) {
  const descriptionId = useId();

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
        <AriaDialog
          role={role}
          aria-describedby={description ? descriptionId : undefined}
          className="flex max-h-full min-h-0 flex-col outline-none"
        >
          {({ close }) => (
            <>
              <div className="flex items-start justify-between gap-4 px-4 pt-4 tablet:px-6 tablet:pt-6">
                <div className="flex min-w-0 flex-col gap-1">
                  <Heading
                    slot="title"
                    className="text-card-heading text-text-primary"
                  >
                    {title}
                  </Heading>
                  {description && (
                    <div
                      id={descriptionId}
                      className="text-body-sm text-text-secondary"
                    >
                      {description}
                    </div>
                  )}
                </div>
                {showCloseButton && (
                  <IconButton
                    label={closeLabel}
                    icon={CloseIcon}
                    onPress={close}
                  />
                )}
              </div>
              {children !== undefined && children !== null ? (
                <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 text-body-sm tablet:px-6">
                  {typeof children === "function" ? children(close) : children}
                </div>
              ) : (
                <div className="pb-4" />
              )}
              {actions && (
                <div className="flex flex-col-reverse gap-2 border-t border-border-subtle px-4 py-4 tablet:flex-row tablet:justify-end tablet:px-6">
                  {typeof actions === "function" ? actions(close) : actions}
                </div>
              )}
            </>
          )}
        </AriaDialog>
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
