"use client";

import {
  ErrorState,
  LoadingRegion,
  Skeleton,
  SkeletonCard,
  SkeletonText,
} from "@/design-system/components";

import { PageContainer } from "./PageContainer";

// Shell-level loading and error presentations (T00-08) for the Next.js
// loading.tsx / error.tsx boundaries of each experience. They render inside
// the shell, so header and navigation stay usable. Reuse the T00-07A
// LoadingRegion, Skeleton and ErrorState — no second loading system.
// The error view never shows the error message or stack: only a fixed,
// user-safe text and, when present, the opaque server digest as a reference.

export function ShellLoading({ label = "Loading page" }: { label?: string }) {
  return (
    <PageContainer>
      <LoadingRegion label={label}>
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-3">
            <Skeleton width="1/3" height="heading" />
            <Skeleton width="1/2" />
          </div>
          <SkeletonText lines={2} />
          <SkeletonCard />
        </div>
      </LoadingRegion>
    </PageContainer>
  );
}

export type ShellErrorProps = {
  onRetry: () => void;
  homeHref: string;
  /** Opaque server reference (Next.js error digest). Never the message. */
  reference?: string;
};

export function ShellError({ onRetry, homeHref, reference }: ShellErrorProps) {
  return (
    <PageContainer>
      <h1 className="sr-only">Page error</h1>
      <ErrorState
        title="This page could not be loaded"
        description="Something went wrong while loading this page. Try again, or go back to the home page."
        onRetry={onRetry}
        backHref={homeHref}
        backLabel="Go to home"
        reference={reference}
      />
    </PageContainer>
  );
}
