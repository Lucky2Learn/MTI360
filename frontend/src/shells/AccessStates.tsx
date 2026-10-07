"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";

import { Button, EmptyState, ErrorState } from "@/design-system/components";
import { BackIcon, CompassIcon } from "@/design-system/icons";

import { PageContainer } from "./PageContainer";

// In-shell access states (T01-05 UI contract §8.1, §8.2). Rendered at the
// requested URL (no redirect), inside the application shell, with exactly one
// visually hidden h1 and the visible state title as h2.
// - AUTHZ-01 Access denied: the same view for every denied page. It never
//   names a permission, a role, the requirement or why access is missing.
// - RESOURCE-02 Not found: one answer for "does not exist", "another
//   institute" and "a campus outside your access" (IDOR protection, D-B1).
// After a client-side navigation focus moves to the h1 (on a first page load
// focus is left alone, so the skip link stays the first tab stop).

function useNavigationFocus() {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const active = document.activeElement;
    if (active && active !== document.body) ref.current?.focus();
  }, []);
  return ref;
}

const noSubscription = () => () => undefined;

export type AccessStateProps = {
  homeHref: string;
  /** Label of the way home (default "Go to dashboard"). */
  homeLabel?: string;
};

export type ShellAccessDeniedProps = AccessStateProps & {
  /** Who to ask; defaults to the tenant wording (T01-09B: platform). */
  description?: string;
};

const TENANT_DENIED =
  "Your access in this institute doesn't include this page. If you need it, ask your institute administrator.";

export function ShellAccessDenied({
  homeHref,
  homeLabel = "Go to dashboard",
  description = TENANT_DENIED,
}: ShellAccessDeniedProps) {
  const heading = useNavigationFocus();
  return (
    <PageContainer>
      <h1 ref={heading} tabIndex={-1} className="sr-only">
        Access denied
      </h1>
      <ErrorState
        kind="permission"
        title="You don't have access to this page"
        description={description}
        backHref={homeHref}
        backLabel={homeLabel}
      />
    </PageContainer>
  );
}

export function ShellNotFound({
  homeHref,
  homeLabel = "Go to dashboard",
}: AccessStateProps) {
  const heading = useNavigationFocus();
  // Only with a previous entry in this tab (never on the server render).
  const canGoBack = useSyncExternalStore(
    noSubscription,
    () => window.history.length > 1,
    () => false,
  );
  return (
    <PageContainer>
      <h1 ref={heading} tabIndex={-1} className="sr-only">
        Not found
      </h1>
      <EmptyState
        titleAs="h2"
        icon={CompassIcon}
        title="Page not found"
        description="This page or item doesn't exist, or it's no longer available."
        primaryAction={<Button href={homeHref}>{homeLabel}</Button>}
        secondaryAction={
          canGoBack ? (
            <Button
              variant="secondary"
              iconStart={BackIcon}
              onPress={() => window.history.back()}
            >
              Go back
            </Button>
          ) : undefined
        }
      />
    </PageContainer>
  );
}
