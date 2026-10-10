import { PageContainer, PageContent, PageHeader } from "@/shells";
import type { BreadcrumbItem } from "@/shells";

import type { ReactNode } from "react";

// DataListTemplate — page template T02 Data List (Phase 02-1; DESIGN-SYSTEM.md
// templates, CLAUDE.md §25, §33). One frame for every record list:
//
//   PageHeader (breadcrumbs → h1 → description → actions, primary last)
//   → toolbar (view tabs, quick filters, FilterBar with Search)
//   → content (DataTable with mobile cards, a board, or an empty/error state)
//   → footer (Pagination)
//
// Wide content width (tables and boards). Responsive behaviour lives in the
// composed components: FilterBar moves filters into a Drawer on mobile and
// DataTable turns rows into cards. Business neutral: labels come from the page.

export type DataListTemplateProps = {
  title: string;
  description?: ReactNode;
  breadcrumbs?: BreadcrumbItem[];
  /** Page actions, primary action last. */
  actions?: ReactNode;
  /** View tabs, quick filters and the FilterBar. */
  toolbar?: ReactNode;
  children: ReactNode;
  /** Usually <Pagination />. */
  footer?: ReactNode;
};

export function DataListTemplate({
  title,
  description,
  breadcrumbs,
  actions,
  toolbar,
  children,
  footer,
}: DataListTemplateProps) {
  return (
    <PageContainer width="wide">
      <PageHeader
        title={title}
        description={description}
        breadcrumbs={breadcrumbs}
        actions={actions}
      />
      <PageContent>
        {toolbar && (
          <div className="flex min-w-0 flex-col gap-4">{toolbar}</div>
        )}
        <div className="flex min-w-0 flex-col gap-4">
          {children}
          {footer}
        </div>
      </PageContent>
    </PageContainer>
  );
}
