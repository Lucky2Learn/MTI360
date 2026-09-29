import { ActionBar } from "@/design-system/layout";

import { Breadcrumbs, type BreadcrumbItem } from "./Breadcrumbs";

import type { ReactNode } from "react";

// PageHeader (T00-08; CLAUDE.md §31): breadcrumbs → title (the page's only
// h1) with an optional status badge → description → primary/secondary
// actions → optional secondary content (tabs, filters, summary). Business
// neutral: every label is supplied by the page. Actions stack full width on
// mobile (primary on top). From tablet they sit beside the title while the
// title keeps at least 24rem; otherwise they wrap onto their own row below it
// (T00-09), so a long title is never squeezed into a narrow column.

export type PageHeaderProps = {
  title: string;
  description?: ReactNode;
  breadcrumbs?: BreadcrumbItem[];
  /** Status indicator next to the title, e.g. <Badge tone="success">Active</Badge>. */
  status?: ReactNode;
  /** Page actions, primary action last (it sits at the end of the row). */
  actions?: ReactNode;
  /** Secondary content below the title block (tabs, filters, summaries). */
  children?: ReactNode;
};

export function PageHeader({
  title,
  description,
  breadcrumbs,
  status,
  actions,
  children,
}: PageHeaderProps) {
  return (
    <div className="flex min-w-0 flex-col gap-4">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <Breadcrumbs items={breadcrumbs} />
      )}
      <div className="flex flex-col gap-4 tablet:flex-row tablet:flex-wrap tablet:items-start tablet:justify-between">
        <div className="flex min-w-0 flex-col gap-2 tablet:flex-1 tablet:basis-96">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="min-w-0 text-section break-words text-text-primary tablet:text-page-title">
              {title}
            </h1>
            {status}
          </div>
          {description && (
            <div className="text-body text-text-secondary">{description}</div>
          )}
        </div>
        {actions && <ActionBar>{actions}</ActionBar>}
      </div>
      {children}
    </div>
  );
}
