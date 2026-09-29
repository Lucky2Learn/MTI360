"use client";

import {
  Text,
  UNSTABLE_Toast as AriaToast,
  UNSTABLE_ToastContent as AriaToastContent,
  UNSTABLE_ToastQueue as AriaToastQueue,
  UNSTABLE_ToastRegion as AriaToastRegion,
} from "react-aria-components";

import { Button } from "@/design-system/components/Button";
import { IconButton } from "@/design-system/components/IconButton";
import { toneIcon, toneIndicator } from "@/design-system/components/tone";
import { CloseIcon } from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

// Toast (DESIGN-SYSTEM.md §49, §86; T00-07C). Wraps React Aria's toast
// primitives, which are still exported as UNSTABLE_* in react-aria-components
// 1.21.1 (pinned); the MTI 360 API below insulates screens from future changes
// (ADR-0008). The region is an ARIA landmark that announces new toasts,
// supports F6 navigation into the region, pauses timers while hovered or
// focused, and restores focus when the last toast closes.
//
// Timing (WCAG 2.2.1): success/info close after 5 s and warning after 8 s by
// default; error toasts and toasts with an action stay until dismissed, so
// nobody is forced to act within a time limit. Up to three are visible; the
// rest wait in the queue.
//
// The global region is mounted by the application shell (T00-08); the
// design-system showcase mounts its own.

export type ToastTone = "success" | "info" | "warning" | "error";

export type ToastAction = { label: string; onAction: () => void };

export type ToastContent = {
  tone: ToastTone;
  title: string;
  description?: string;
  action?: ToastAction;
};

export type ToastOptions = {
  /** Milliseconds before auto-dismiss; `null` keeps the toast until dismissed. */
  timeout?: number | null;
  onClose?: () => void;
};

export type ToastQueue = AriaToastQueue<ToastContent>;

const DEFAULT_TIMEOUT: Record<ToastTone, number | null> = {
  success: 5000,
  info: 5000,
  warning: 8000,
  error: null,
};

export function createToastQueue(): ToastQueue {
  return new AriaToastQueue<ToastContent>({ maxVisibleToasts: 3 });
}

/** Default application queue (rendered by <ToastRegion />). */
export const toastQueue = createToastQueue();

export function showToast(
  content: ToastContent,
  options: ToastOptions = {},
  queue: ToastQueue = toastQueue,
): string {
  const fallback = content.action ? null : DEFAULT_TIMEOUT[content.tone];
  const timeout = options.timeout === undefined ? fallback : options.timeout;
  return queue.add(content, {
    timeout: timeout ?? undefined,
    onClose: options.onClose,
  });
}

type Shorthand = (
  title: string,
  details?: Omit<ToastContent, "tone" | "title"> & ToastOptions,
) => string;

const shorthand =
  (tone: ToastTone): Shorthand =>
  (title, details = {}) => {
    const { timeout, onClose, ...rest } = details;
    return showToast({ tone, title, ...rest }, { timeout, onClose });
  };

/** Convenience API on the default queue: toast.success("Payment recorded"). */
export const toast = {
  success: shorthand("success"),
  info: shorthand("info"),
  warning: shorthand("warning"),
  error: shorthand("error"),
  dismiss: (key: string) => toastQueue.close(key),
};

export type ToastRegionProps = {
  queue?: ToastQueue;
  /** Accessible name of the notifications landmark. */
  label?: string;
};

export function ToastRegion({
  queue = toastQueue,
  label = "Notifications",
}: ToastRegionProps) {
  return (
    <AriaToastRegion
      queue={queue}
      aria-label={label}
      // a11y-focus: region landmark (F6); each toast draws the focus ring
      className="fixed inset-x-4 bottom-4 z-(--z-toast) flex flex-col-reverse gap-2 outline-none tablet:right-4 tablet:left-auto tablet:w-96"
    >
      {({ toast: item }) => {
        const Icon = toneIcon[item.content.tone]!;
        return (
          <AriaToast
            toast={item}
            className={cx(
              "flex items-start gap-3 rounded-lg border border-l-4 border-border-default bg-surface-elevated p-4 text-text-primary shadow-lg outline-none",
              "data-focus-visible:outline-solid data-focus-visible:outline-(length:--focus-ring-width) data-focus-visible:outline-focus-ring",
              "transition-opacity starting:opacity-0 motion-reduce:transition-none",
              {
                success: "border-l-success",
                info: "border-l-info",
                warning: "border-l-warning",
                error: "border-l-error",
              }[item.content.tone],
            )}
          >
            <Icon
              aria-hidden="true"
              className={cx(
                "size-5 shrink-0",
                toneIndicator[item.content.tone],
              )}
            />
            <AriaToastContent className="flex min-w-0 flex-1 flex-col gap-1">
              <Text slot="title" className="text-body-sm font-semibold">
                {item.content.title}
              </Text>
              {item.content.description && (
                <Text
                  slot="description"
                  className="text-body-sm text-text-secondary"
                >
                  {item.content.description}
                </Text>
              )}
              {item.content.action && (
                <div className="pt-1">
                  <Button
                    variant="tertiary"
                    size="sm"
                    onPress={() => {
                      item.content.action?.onAction();
                      queue.close(item.key);
                    }}
                  >
                    {item.content.action.label}
                  </Button>
                </div>
              )}
            </AriaToastContent>
            <IconButton
              slot="close"
              label="Dismiss notification"
              icon={CloseIcon}
            />
          </AriaToast>
        );
      }}
    </AriaToastRegion>
  );
}
