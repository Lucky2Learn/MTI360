import { EmptyIcon, type IconComponent } from "@/design-system/icons";

import type { ReactNode, Ref } from "react";

// EmptyState (DESIGN-SYSTEM.md §59, UI-SCREENS.md §10): explains what is
// empty, why, and what the user can do next. Icon · Title · Explanation ·
// Primary action. The icon stays subtle (maritime references are optional,
// e.g. CompassIcon). Server-component compatible; pass Buttons as actions.
// T01-09A: `titleAs="h1"` when it replaces a whole screen's content, and
// `titleRef` for focus after replacement (the title takes tabIndex=-1).

type HeadingLevel = "h1" | "h2" | "h3" | "h4";

export type EmptyStateProps = {
  /** What is empty, e.g. "No leads yet". */
  title: string;
  /** Why it is empty and what happens next. */
  description: ReactNode;
  icon?: IconComponent;
  primaryAction?: ReactNode;
  secondaryAction?: ReactNode;
  titleAs?: HeadingLevel;
  /** Programmatic focus target (tabIndex=-1) for focus after replacement. */
  titleRef?: Ref<HTMLHeadingElement>;
};

export function EmptyState({
  title,
  description,
  icon: Icon = EmptyIcon,
  primaryAction,
  secondaryAction,
  titleAs: Heading = "h3",
  titleRef,
}: EmptyStateProps) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-4 py-12 text-center">
      <span
        aria-hidden="true"
        className="flex size-12 items-center justify-center rounded-full bg-surface-secondary text-accent-maritime"
      >
        <Icon className="size-6" />
      </span>
      <div className="flex flex-col gap-2">
        <Heading
          ref={titleRef}
          tabIndex={titleRef ? -1 : undefined}
          className="text-card-heading text-text-primary"
        >
          {title}
        </Heading>
        <div className="text-body-sm text-text-secondary">{description}</div>
      </div>
      {(primaryAction || secondaryAction) && (
        <div className="flex w-full flex-col-reverse items-stretch gap-2 tablet:w-auto tablet:flex-row tablet:items-center">
          {secondaryAction}
          {primaryAction}
        </div>
      )}
    </div>
  );
}
