"use client";

import { Button } from "@/design-system/components";

import type { ReactNode } from "react";

// Print views of a fee invoice and a receipt (Phase 02-5; readiness plan §2,
// §4: a print stylesheet, no PDF dependency). On screen: a toolbar to print
// or go back, above the document. On paper: only the document
// ([data-print-region], globals.css), single column, in light ink.

export function PrintView({
  backHref,
  backLabel,
  printLabel,
  children,
}: {
  backHref: string;
  backLabel: string;
  printLabel: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-6">
      <div
        data-print-hide
        className="flex flex-col-reverse gap-2 tablet:flex-row tablet:justify-end"
      >
        <Button variant="secondary" href={backHref}>
          {backLabel}
        </Button>
        <Button onPress={() => window.print()}>{printLabel}</Button>
      </div>
      <article
        data-print-region
        className="mx-auto flex w-full max-w-3xl min-w-0 flex-col gap-6 text-text-primary"
      >
        {children}
      </article>
    </div>
  );
}

/** A labelled value of a printed document (definition list item). */
export function PrintTerm({
  term,
  children,
}: {
  term: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-caption text-text-secondary">{term}</dt>
      <dd className="text-body-sm break-words text-text-primary">{children}</dd>
    </div>
  );
}
