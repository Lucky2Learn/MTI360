import { Button, EmptyState } from "@/design-system/components";
import { CompassIcon } from "@/design-system/icons";

import { PageContainer, PageContent } from "./PageContainer";
import { PageHeader } from "./PageHeader";
import { ToastExample } from "./ToastExample";

import type { ExperiencePage } from "./experiences";

// ExperiencePlaceholder (T00-08): body of every experience route until its
// module is built. It demonstrates the page structure (breadcrumbs → header →
// content) and states plainly that the page is not implemented. It contains
// no business logic or data.

export function ExperiencePlaceholder({ page }: { page: ExperiencePage }) {
  const { experience, item, trail, isHome } = page;
  const breadcrumbs = isHome
    ? undefined
    : [
        { label: experience.label, href: experience.basePath },
        ...trail.map((entry, index) =>
          index === trail.length - 1
            ? { label: entry.label }
            : { label: entry.label, href: entry.href },
        ),
      ];

  return (
    <PageContainer width={experience.pageWidth}>
      <PageHeader
        breadcrumbs={breadcrumbs}
        title={item.label}
        description={
          isHome
            ? `${experience.label} — application shell foundation.`
            : undefined
        }
      />
      <PageContent>
        <EmptyState
          icon={CompassIcon}
          titleAs="h2"
          title={`${item.label} is not built yet`}
          description="This page is a navigation placeholder. The module is delivered in a later phase."
          primaryAction={
            isHome ? (
              <ToastExample />
            ) : (
              <Button href={experience.basePath} variant="secondary">
                {`Back to ${experience.label}`}
              </Button>
            )
          }
        />
      </PageContent>
    </PageContainer>
  );
}
