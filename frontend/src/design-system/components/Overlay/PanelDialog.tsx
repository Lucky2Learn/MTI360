"use client";

import { useId, type ReactNode } from "react";
import { Dialog as AriaDialog, Heading } from "react-aria-components";

import { IconButton } from "@/design-system/components/IconButton";
import { CloseIcon } from "@/design-system/icons";

// Internal: header / scrolling body / actions layout shared by Dialog,
// AlertDialog and Drawer (T00-07C). Renders the React Aria Dialog (role,
// labelling by the title, description via aria-describedby, focus scope).

type Close = () => void;

export type PanelDialogProps = {
  title: string;
  description?: ReactNode;
  children?: ReactNode | ((close: Close) => ReactNode);
  actions?: ReactNode | ((close: Close) => ReactNode);
  showCloseButton?: boolean;
  closeLabel?: string;
  role?: "dialog" | "alertdialog";
};

export function PanelDialog({
  title,
  description,
  children,
  actions,
  showCloseButton = true,
  closeLabel = "Close dialog",
  role = "dialog",
}: PanelDialogProps) {
  const descriptionId = useId();
  return (
    <AriaDialog
      role={role}
      aria-describedby={description ? descriptionId : undefined}
      className="flex max-h-full min-h-0 flex-1 flex-col outline-none"
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
              <IconButton label={closeLabel} icon={CloseIcon} onPress={close} />
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
  );
}
