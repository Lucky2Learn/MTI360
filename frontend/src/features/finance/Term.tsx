import type { ReactNode } from "react";

// A term and its value in a detail card's definition list (the course and
// student detail pattern). Server-component compatible.
export function Term({
  term,
  children,
}: {
  term: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1 tablet:flex-row tablet:gap-6">
      <dt className="text-body-sm text-text-secondary tablet:w-40 tablet:shrink-0">
        {term}
      </dt>
      <dd className="min-w-0 text-body-sm break-words whitespace-pre-wrap text-text-primary">
        {children}
      </dd>
    </div>
  );
}
