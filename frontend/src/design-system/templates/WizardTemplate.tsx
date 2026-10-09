import Link from "next/link";

import { CheckIcon } from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";
import { PageContainer, PageContent, PageHeader } from "@/shells";
import type { BreadcrumbItem } from "@/shells";

import type { ReactNode } from "react";

// WizardTemplate — page template T05 Wizard (Phase 02-2; DESIGN-SYSTEM.md
// templates, CLAUDE.md §25; ADR-0021 §14). A long task split into steps that
// are saved one at a time, so it can be left and resumed:
//
//   PageHeader (breadcrumbs → h1 → description)
//   → step navigation: an ordered list of links ("Step 2 of 5" on mobile,
//     the full list from tablet). Each step is a URL (?step=…) so Back,
//     bookmarks and resuming work; the current step has aria-current="step";
//     complete steps carry a check icon AND the words "completed" for
//     assistive technology (never colour alone, WCAG 1.4.1).
//   → the step's content (usually a form with FormActions)
//
// Standard content width (forms). Business neutral: steps come from the page.

export type WizardStep = {
  id: string;
  label: string;
  href: string;
  complete?: boolean;
};

export type WizardTemplateProps = {
  title: string;
  description?: ReactNode;
  breadcrumbs?: BreadcrumbItem[];
  status?: ReactNode;
  steps: WizardStep[];
  currentStep: string;
  /** Accessible name of the step navigation. */
  stepsLabel?: string;
  children: ReactNode;
};

export function WizardTemplate({
  title,
  description,
  breadcrumbs,
  status,
  steps,
  currentStep,
  stepsLabel = "Steps",
  children,
}: WizardTemplateProps) {
  const index = Math.max(
    0,
    steps.findIndex((step) => step.id === currentStep),
  );
  const current = steps[index];
  return (
    <PageContainer width="standard">
      <PageHeader
        title={title}
        description={description}
        breadcrumbs={breadcrumbs}
        status={status}
      />
      <PageContent>
        <nav aria-label={stepsLabel} className="min-w-0">
          <p className="text-body-sm text-text-secondary tablet:hidden">
            {`Step ${index + 1} of ${steps.length}: ${current?.label ?? ""}`}
          </p>
          <ol className="hidden min-w-0 flex-wrap gap-2 tablet:flex">
            {steps.map((step, position) => {
              const isCurrent = step.id === current?.id;
              return (
                <li key={step.id} className="min-w-0">
                  <Link
                    href={step.href}
                    aria-current={isCurrent ? "step" : undefined}
                    className={cx(
                      "flex min-h-control-lg items-center gap-2 rounded-md border px-3 py-2 text-body-sm",
                      focusRing,
                      isCurrent
                        ? "border-border-strong bg-surface-selected font-medium text-text-primary"
                        : "border-border-subtle text-text-secondary hover:bg-surface-hover hover:text-text-primary",
                    )}
                  >
                    <span
                      aria-hidden="true"
                      className="flex size-6 shrink-0 items-center justify-center rounded-full border border-border-subtle text-caption"
                    >
                      {step.complete ? (
                        <CheckIcon className="size-4" />
                      ) : (
                        position + 1
                      )}
                    </span>
                    <span className="min-w-0 break-words">{step.label}</span>
                    {step.complete && (
                      <span className="sr-only"> (completed)</span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ol>
        </nav>
        <div className="flex min-w-0 flex-col gap-6">{children}</div>
      </PageContent>
    </PageContainer>
  );
}
