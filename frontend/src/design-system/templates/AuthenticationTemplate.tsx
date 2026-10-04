import { Card, CardBody, CardHeader } from "@/design-system/components";
import { CompassIcon } from "@/design-system/icons";
import { ThemeSelector } from "@/design-system/theme/ThemeSelector";
import { MAIN_CONTENT_ID, SkipNavigation } from "@/shells/SkipNavigation";

import type { ReactNode } from "react";

// AuthenticationTemplate — page template T16 (T01-09A; T01-04 UI contract §7,
// DESIGN-SYSTEM.md §68, §90). One frame for every tenant authentication
// screen:
//
//   SkipNavigation → banner (MTI 360 wordmark, not a link)
//   → main#main-content: form column (Card, max-w-md) + brand panel
//     (desktop and up; after the form in the DOM; decorative, no headings,
//     nothing focusable)
//   → contentinfo (ThemeSelector · © MTI 360).
//
// Exactly one h1: the card title — or, when a state replaces the content
// (`title` omitted), the ErrorState / EmptyState title rendered as h1.
// No tenant branding before sign-in (§7.1, S14). Semantic tokens only.

export type AuthenticationTemplateProps = {
  /** Card title (the page h1). Omit when the content brings its own h1. */
  title?: ReactNode;
  description?: ReactNode;
  /** Notice above the content (e.g. an Alert from ?reason=). */
  notice?: ReactNode;
  children: ReactNode;
  /** Secondary links below the card. */
  footer?: ReactNode;
};

export function AuthenticationTemplate({
  title,
  description,
  notice,
  children,
  footer,
}: AuthenticationTemplateProps) {
  return (
    <div className="flex min-h-dvh flex-col bg-background-primary">
      <SkipNavigation />
      <header className="flex h-16 shrink-0 items-center border-b border-border-subtle bg-surface-primary px-4 tablet:px-6 desktop:px-8">
        <p className="flex items-center gap-2 text-body font-bold text-text-primary">
          <span
            aria-hidden="true"
            className="flex size-8 items-center justify-center rounded-md bg-brand-primary text-text-inverse"
          >
            <CompassIcon className="size-5" />
          </span>
          MTI 360
        </p>
      </header>
      <main
        id={MAIN_CONTENT_ID}
        tabIndex={-1}
        // a11y-focus: skip-link target (tabIndex -1), programmatic focus only
        className="grid min-w-0 flex-1 grid-cols-1 outline-none desktop:grid-cols-2"
      >
        <div className="flex min-w-0 justify-center px-4 py-8 tablet:px-6 tablet:py-12 desktop:px-8 large:items-center">
          <div className="flex w-full max-w-md min-w-0 flex-col gap-4 break-words">
            <Card elevation="sm" padding="lg">
              {title && (
                <CardHeader
                  titleAs="h1"
                  title={title}
                  description={description}
                />
              )}
              <CardBody>
                {notice}
                {children}
              </CardBody>
            </Card>
            {footer && (
              <div className="flex flex-col items-start gap-1">{footer}</div>
            )}
          </div>
        </div>
        <div
          aria-hidden="true"
          className="hidden min-w-0 flex-col justify-center border-l border-border-subtle bg-background-secondary px-8 desktop:flex large:px-16"
        >
          <div className="flex max-w-md flex-col gap-4">
            <div className="flex items-center gap-2 text-accent-maritime">
              <CompassIcon className="size-5 shrink-0" />
              <span className="h-px w-16 bg-accent-maritime" />
              <span className="h-0.5 w-6 bg-accent-brass" />
            </div>
            <p className="text-section text-text-primary">
              Acquire Students. Simplify Operations. Grow Your Institute.
            </p>
            <p className="text-body text-text-secondary">
              The complete growth and operations platform for maritime training
              institutes.
            </p>
          </div>
        </div>
      </main>
      <footer className="flex flex-col gap-4 border-t border-border-subtle bg-surface-primary px-4 py-4 tablet:flex-row tablet:items-end tablet:justify-between tablet:px-6 desktop:px-8">
        <ThemeSelector />
        <p className="text-caption text-text-muted">© MTI 360</p>
      </footer>
    </div>
  );
}
