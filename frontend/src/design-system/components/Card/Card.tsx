import { cx } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// Card (DESIGN-SYSTEM.md §43). Groups related content on a surface: KPIs,
// summaries, records, actions, insights. Not a default wrapper — use it only
// when grouping helps. Server-component compatible (no client code).

export type CardElevation = "none" | "sm" | "md";
export type CardPadding = "none" | "md" | "lg";
type HeadingLevel = "h2" | "h3" | "h4";

const elevations: Record<CardElevation, string> = {
  none: "",
  sm: "shadow-sm",
  md: "shadow-md",
};

// Mobile-first padding on the 4px grid (16 → 24 px from tablet).
const paddings: Record<CardPadding, string> = {
  none: "",
  md: "p-4 tablet:p-6",
  lg: "p-6 tablet:p-8",
};

export type CardProps = {
  children: ReactNode;
  /** Semantic element: section/article when the card is a standalone unit. */
  as?: "div" | "section" | "article";
  elevation?: CardElevation;
  padding?: CardPadding;
  /** Accessible name for section/article cards (id of the title). */
  "aria-labelledby"?: string;
  "aria-label"?: string;
};

export function Card({
  children,
  as: Element = "div",
  elevation = "sm",
  padding = "md",
  ...aria
}: CardProps) {
  return (
    <Element
      {...aria}
      className={cx(
        "flex flex-col gap-4 rounded-xl border border-border-subtle bg-surface-primary text-text-primary",
        elevations[elevation],
        paddings[padding],
      )}
    >
      {children}
    </Element>
  );
}

export type CardHeaderProps = {
  title: ReactNode;
  titleAs?: HeadingLevel;
  /** Id for the title, to label a section/article card via aria-labelledby. */
  titleId?: string;
  description?: ReactNode;
  /** Header actions (buttons, menus); wraps below the title on small screens. */
  actions?: ReactNode;
};

export function CardHeader({
  title,
  titleAs: Heading = "h3",
  titleId,
  description,
  actions,
}: CardHeaderProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex min-w-0 flex-col gap-1">
        <Heading id={titleId} className="text-card-heading text-text-primary">
          {title}
        </Heading>
        {description && (
          <p className="text-body-sm text-text-secondary">{description}</p>
        )}
      </div>
      {actions && (
        <div className="flex shrink-0 items-center gap-2">{actions}</div>
      )}
    </div>
  );
}

export function CardBody({ children }: { children: ReactNode }) {
  return <div className="flex flex-col gap-3 text-body-sm">{children}</div>;
}

export function CardFooter({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border-subtle pt-4">
      {children}
    </div>
  );
}
