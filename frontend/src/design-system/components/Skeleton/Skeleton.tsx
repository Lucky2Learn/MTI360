import { cx } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// Skeleton (DESIGN-SYSTEM.md §58): placeholders for structured content while
// it loads; layout stays stable. Skeleton shapes are decorative (aria-hidden);
// the surrounding LoadingRegion announces the loading state once. The pulse
// runs only when the user has not asked for reduced motion.
// Server-component compatible.

type Width = "full" | "3/4" | "1/2" | "1/3" | "1/4";
type Height = "text" | "heading" | "control" | "block";

const widths: Record<Width, string> = {
  full: "w-full",
  "3/4": "w-3/4",
  "1/2": "w-1/2",
  "1/3": "w-1/3",
  "1/4": "w-1/4",
};

const heights: Record<Height, string> = {
  text: "h-4",
  heading: "h-6",
  control: "h-control-md",
  block: "h-24",
};

export type SkeletonProps = {
  width?: Width;
  height?: Height;
  shape?: "rounded" | "circle";
};

export function Skeleton({
  width = "full",
  height = "text",
  shape = "rounded",
}: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      data-skeleton=""
      className={cx(
        "bg-border-subtle motion-safe:animate-pulse",
        shape === "circle"
          ? "size-10 shrink-0 rounded-full"
          : cx("rounded-md", widths[width], heights[height]),
      )}
    />
  );
}

export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div aria-hidden="true" className="flex flex-col gap-2">
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton
          key={index}
          width={index === lines - 1 && lines > 1 ? "3/4" : "full"}
        />
      ))}
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div
      aria-hidden="true"
      className="flex flex-col gap-4 rounded-xl border border-border-subtle bg-surface-primary p-4 tablet:p-6"
    >
      <div className="flex items-center gap-3">
        <Skeleton shape="circle" />
        <div className="flex flex-1 flex-col gap-2">
          <Skeleton width="1/2" height="heading" />
          <Skeleton width="1/3" />
        </div>
      </div>
      <SkeletonText lines={3} />
    </div>
  );
}

export function SkeletonTableRows({
  rows = 5,
  columns = 4,
}: {
  rows?: number;
  columns?: number;
}) {
  return (
    <div
      aria-hidden="true"
      className="flex flex-col divide-y divide-border-subtle"
    >
      {Array.from({ length: rows }, (_, row) => (
        <div key={row} className="flex gap-4 py-3">
          {Array.from({ length: columns }, (_, column) => (
            <Skeleton key={column} width={column === 0 ? "1/3" : "1/4"} />
          ))}
        </div>
      ))}
    </div>
  );
}

export type LoadingRegionProps = {
  /** Announced once, e.g. "Loading students". */
  label: string;
  /** Skeleton placeholders shaped like the content that is loading. */
  children: ReactNode;
};

/** Wraps skeletons: announces the loading state politely and marks the region busy. */
export function LoadingRegion({ label, children }: LoadingRegionProps) {
  return (
    <div role="status" aria-busy="true" aria-live="polite">
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}
