"use client";

import { useId, type ReactNode, type Ref } from "react";

import { Button } from "@/design-system/components/Button";
import {
  BackIcon,
  ErrorIcon,
  LockIcon,
  RetryIcon,
  SupportIcon,
} from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

// ErrorState (DESIGN-SYSTEM.md §57, §60; UI-SCREENS.md §10; CLAUDE.md §37).
// Answers: What happened? What was saved? What can I do? Can I retry?
// Offers Retry / Go back / Contact support where applicable; the actions
// wrap when the container is narrower than one row of buttons (T00-09).
//
// Security: only caller-supplied, user-safe text is rendered — never an Error
// object, stack trace, SQL, provider payload or internal detail (the props
// accept strings/ReactNode, not Error). An optional correlation ID lets
// support find the server-side log entry.
//
// `kind="permission"` is the permission-restricted presentation (§57); the
// authorization decision itself is always made server-side.
//
// T01-09A: `titleAs="h1"` when the state replaces a whole screen's content
// (T16 authentication screens), and `titleRef` to move focus to the title
// after content was replaced (the title then takes tabIndex=-1).

type HeadingLevel = "h1" | "h2" | "h3";

export type ErrorStateProps = {
  kind?: "error" | "permission";
  /** What happened, in plain language. */
  title: string;
  /** What the user can do / why. */
  description?: ReactNode;
  /** What was (not) saved, e.g. "Your draft was saved." */
  savedState?: string;
  onRetry?: () => void;
  retryLabel?: string;
  isRetrying?: boolean;
  backHref?: string;
  backLabel?: string;
  supportHref?: string;
  supportLabel?: string;
  /** Request/correlation reference for support (not a technical message). */
  reference?: string;
  titleAs?: HeadingLevel;
  /** Programmatic focus target (tabIndex=-1) for focus after replacement. */
  titleRef?: Ref<HTMLHeadingElement>;
};

export function ErrorState({
  kind = "error",
  title,
  description,
  savedState,
  onRetry,
  retryLabel = "Try again",
  isRetrying = false,
  backHref,
  backLabel = "Go back",
  supportHref,
  supportLabel = "Contact support",
  reference,
  titleAs: Heading = "h2",
  titleRef,
}: ErrorStateProps) {
  const titleId = useId();
  const Icon = kind === "permission" ? LockIcon : ErrorIcon;

  return (
    <section
      aria-labelledby={titleId}
      className="mx-auto flex max-w-lg flex-col items-center gap-4 px-4 py-12 text-center"
    >
      <span
        aria-hidden="true"
        className={cx(
          "flex size-12 items-center justify-center rounded-full",
          kind === "permission"
            ? "bg-surface-secondary text-text-secondary"
            : "bg-error-surface text-error",
        )}
      >
        <Icon className="size-6" />
      </span>
      <div className="flex flex-col gap-2">
        <Heading
          id={titleId}
          ref={titleRef}
          tabIndex={titleRef ? -1 : undefined}
          className="text-card-heading text-text-primary"
        >
          {title}
        </Heading>
        {description && (
          <div className="text-body-sm text-text-secondary">{description}</div>
        )}
        {savedState && (
          <p className="text-body-sm font-medium text-text-primary">
            {savedState}
          </p>
        )}
      </div>
      {(onRetry || backHref || supportHref) && (
        <div className="flex w-full flex-col items-stretch gap-2 tablet:w-auto tablet:flex-row tablet:flex-wrap tablet:items-center tablet:justify-center">
          {onRetry && (
            <Button
              iconStart={RetryIcon}
              onPress={onRetry}
              isPending={isRetrying}
            >
              {retryLabel}
            </Button>
          )}
          {backHref && (
            <Button href={backHref} variant="secondary" iconStart={BackIcon}>
              {backLabel}
            </Button>
          )}
          {supportHref && (
            <Button
              href={supportHref}
              variant="tertiary"
              iconStart={SupportIcon}
            >
              {supportLabel}
            </Button>
          )}
        </div>
      )}
      {reference && (
        <p className="text-caption text-text-muted">
          Reference: <span className="font-mono">{reference}</span>
        </p>
      )}
    </section>
  );
}
