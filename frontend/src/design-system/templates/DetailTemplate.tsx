import { SplitLayout } from "@/design-system/layout";
import { PageContainer, PageContent, PageHeader } from "@/shells";
import type { BreadcrumbItem } from "@/shells";

import type { ReactNode } from "react";

// DetailTemplate — page template T03 Detail (Phase 02-1; DESIGN-SYSTEM.md
// templates, CLAUDE.md §25). One frame for a record's 360 view:
//
//   PageHeader (breadcrumbs → h1 + status badge → description → actions)
//   → main column (the record's details)   | side column (state, owner,
//                                           |  next steps, quick actions)
//   → full-width sections (activity, history)
//
// From desktop (1024px) the side column sits to the right of the main column
// (SplitLayout 2:1). Below desktop everything stacks in DOM order — main,
// side, then the full-width sections — so reading order, focus order and
// visual order are the same at every width (WCAG 1.3.2, 2.4.3).

export type DetailTemplateProps = {
  title: string;
  description?: ReactNode;
  breadcrumbs?: BreadcrumbItem[];
  /** Status next to the title, e.g. <Badge tone="success">Active</Badge>. */
  status?: ReactNode;
  actions?: ReactNode;
  main: ReactNode;
  /** Side column; accessible name of its landmark is `asideLabel`. */
  aside?: ReactNode;
  asideLabel?: string;
  /** Full-width sections after the columns (activity, history). */
  children?: ReactNode;
};

export function DetailTemplate({
  title,
  description,
  breadcrumbs,
  status,
  actions,
  main,
  aside,
  asideLabel = "Summary",
  children,
}: DetailTemplateProps) {
  return (
    <PageContainer width="wide">
      <PageHeader
        title={title}
        description={description}
        breadcrumbs={breadcrumbs}
        status={status}
        actions={actions}
      />
      <PageContent>
        {aside ? (
          <SplitLayout
            ratio="2:1"
            stackBelow="desktop"
            primary={<div className="flex min-w-0 flex-col gap-6">{main}</div>}
            secondary={
              <aside
                aria-label={asideLabel}
                className="flex min-w-0 flex-col gap-6"
              >
                {aside}
              </aside>
            }
          />
        ) : (
          <div className="flex min-w-0 flex-col gap-6">{main}</div>
        )}
        {children}
      </PageContent>
    </PageContainer>
  );
}
