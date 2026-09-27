"use client";

import { Button } from "@/design-system/components/Button";

import { Dialog } from "./Dialog";

import type { ReactElement, ReactNode } from "react";

// AlertDialog — confirmation for consequential or destructive actions
// (DESIGN-SYSTEM.md §62; CLAUDE.md §44; T00-07 D9: "Dialog" confirmation built
// on the modal container). role="alertdialog"; focus starts on Cancel (the
// safest action); Escape cancels; clicking the scrim does not dismiss; the
// confirm action carries an explicit label. Wording is supplied by the caller
// — the component contains no business text.

export type AlertDialogProps = {
  title: string;
  /** The consequence, in plain language. */
  description: ReactNode;
  /** Explicit action label, e.g. "Delete student" (never just "OK"). */
  confirmLabel: string;
  cancelLabel?: string;
  /** "destructive" styles the confirm action with error-strong. */
  tone?: "default" | "destructive";
  onConfirm: () => void;
  onCancel?: () => void;
  /** Keep the dialog open while the confirmed action runs. */
  isPending?: boolean;
  trigger?: ReactElement;
  isOpen?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (isOpen: boolean) => void;
  children?: ReactNode;
};

export function AlertDialog({
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancel",
  tone = "default",
  onConfirm,
  onCancel,
  isPending = false,
  trigger,
  isOpen,
  defaultOpen,
  onOpenChange,
  children,
}: AlertDialogProps) {
  return (
    <Dialog
      role="alertdialog"
      title={title}
      description={description}
      size="sm"
      trigger={trigger}
      isOpen={isOpen}
      defaultOpen={defaultOpen}
      onOpenChange={onOpenChange}
      isDismissable={false}
      showCloseButton={false}
      actions={(close) => (
        <>
          <Button
            variant="secondary"
            // WAI-ARIA alertdialog pattern: initial focus on the least
            // destructive action. Scoped to this dialog only.
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
            isDisabled={isPending}
            onPress={() => {
              onCancel?.();
              close();
            }}
          >
            {cancelLabel}
          </Button>
          <Button
            variant={tone === "destructive" ? "destructive" : "primary"}
            isPending={isPending}
            onPress={() => {
              onConfirm();
              if (isOpen === undefined) close();
            }}
          >
            {confirmLabel}
          </Button>
        </>
      )}
    >
      {children}
    </Dialog>
  );
}
