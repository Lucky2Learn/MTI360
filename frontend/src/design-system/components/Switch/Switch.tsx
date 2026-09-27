"use client";

import { useId, type ReactNode } from "react";
import {
  Switch as AriaSwitch,
  type SwitchProps as AriaSwitchProps,
} from "react-aria-components";

import { CheckIcon, ErrorIcon } from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";

// Switch (T00-07C; DESIGN-SYSTEM.md §42): an on/off setting that applies
// immediately (use Checkbox for choices submitted with a form). React Aria:
// native checkbox with role="switch", Space toggles, label click toggles.
// Controlled (isSelected + onChange) or uncontrolled (defaultSelected).
// On = brand track, thumb moved right with a check mark — not colour alone.
// React Aria's Switch has no validation state; `isInvalid` + `errorMessage`
// show a linked error message for cases where a setting is required.

export type SwitchProps = Omit<
  AriaSwitchProps,
  "className" | "style" | "children"
> & {
  children: ReactNode;
  description?: ReactNode;
  isInvalid?: boolean;
  errorMessage?: string;
};

export function Switch({
  children,
  description,
  isInvalid = false,
  errorMessage,
  ...props
}: SwitchProps) {
  const descriptionId = useId();
  const errorId = useId();
  const showError = isInvalid && Boolean(errorMessage);
  return (
    <div className="flex flex-col gap-1">
      <AriaSwitch
        {...props}
        aria-describedby={
          cx(
            props["aria-describedby"],
            description ? descriptionId : undefined,
            showError ? errorId : undefined,
          ) || undefined
        }
        className={cx(
          "group/switch inline-flex min-h-control-lg w-fit cursor-pointer items-center gap-2 rounded-sm text-body-sm text-text-primary tablet:min-h-control-sm",
          "data-disabled:cursor-not-allowed data-disabled:opacity-50",
          focusRing,
        )}
      >
        {({ isSelected }) => (
          <>
            <span
              aria-hidden="true"
              className={cx(
                "flex h-6 w-10 shrink-0 items-center rounded-full border-2 p-0.5 transition-colors motion-reduce:transition-none",
                isSelected
                  ? "border-brand-primary bg-brand-primary"
                  : "border-border-strong bg-border-strong",
                isInvalid && "border-error",
              )}
            >
              <span
                className={cx(
                  "flex size-4 items-center justify-center rounded-full bg-surface-primary text-brand-primary transition-transform motion-reduce:transition-none",
                  isSelected && "translate-x-4",
                )}
              >
                {isSelected && <CheckIcon className="size-3" strokeWidth={3} />}
              </span>
            </span>
            <span>{children}</span>
          </>
        )}
      </AriaSwitch>
      {description && (
        <p
          id={descriptionId}
          className="pl-12 text-caption text-text-secondary"
        >
          {description}
        </p>
      )}
      {showError && (
        <p
          id={errorId}
          className="flex items-start gap-1 pl-12 text-caption font-medium text-error-text"
        >
          <ErrorIcon aria-hidden="true" className="size-4 shrink-0" />
          <span>{errorMessage}</span>
        </p>
      )}
    </div>
  );
}
