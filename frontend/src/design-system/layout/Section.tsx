import { useId, type ReactNode } from "react";

import { cx } from "@/design-system/lib/cx";

import { ActionBar } from "./ActionBar";
import { gapClasses, type Gap } from "./responsive";

// Section (T00-09): a titled block of page content — heading, optional
// description and actions, then the content. With a title it renders a
// <section> named by its heading; without one it is a plain grouping <div>
// (an unnamed <section> adds nothing for assistive technology). The spacing
// between sections is set by the parent (Stack gap "xl" / "2xl"), not here.
// Header actions (ActionBar) sit beside the title from tablet while the title
// keeps at least 24rem, wrap below it otherwise, and stack full width on mobile.
// Server-component compatible.

type HeadingLevel = "h2" | "h3";

const headingClasses: Record<HeadingLevel, string> = {
  h2: "text-card-heading tablet:text-section",
  h3: "text-card-heading",
};

export type SectionProps = {
  title?: ReactNode;
  /** Heading level: h2 for page sections (default), h3 inside a section. */
  titleAs?: HeadingLevel;
  description?: ReactNode;
  /** Section actions, primary last; stack full width on mobile. */
  actions?: ReactNode;
  /** Space between the header and the content, and between content children. */
  gap?: Gap;
  id?: string;
  children: ReactNode;
};

export function Section({
  title,
  titleAs: Heading = "h2",
  description,
  actions,
  gap = "md",
  id,
  children,
}: SectionProps) {
  const titleId = useId();
  const classes = cx("flex min-w-0 flex-col", gapClasses[gap]);

  if (title === undefined) {
    return (
      <div id={id} className={classes}>
        {children}
      </div>
    );
  }

  return (
    <section id={id} aria-labelledby={titleId} className={classes}>
      <div className="flex min-w-0 flex-col gap-3 tablet:flex-row tablet:flex-wrap tablet:items-start tablet:justify-between">
        <div className="flex min-w-0 flex-col gap-1 tablet:flex-1 tablet:basis-96">
          <Heading
            id={titleId}
            className={cx(
              "break-words text-text-primary",
              headingClasses[Heading],
            )}
          >
            {title}
          </Heading>
          {description && (
            <div className="text-body-sm text-text-secondary">
              {description}
            </div>
          )}
        </div>
        {actions && <ActionBar>{actions}</ActionBar>}
      </div>
      {children}
    </section>
  );
}
