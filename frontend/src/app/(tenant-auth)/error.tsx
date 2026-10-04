"use client";

import { Button, ErrorState } from "@/design-system/components";
import { AuthenticationTemplate } from "@/design-system/templates/AuthenticationTemplate";

// Error boundary of the authentication screens (T01-09A): for example the
// session could not be read for /select-institute. Fixed, user-safe text with
// retry; never the error message (CLAUDE.md §37). Only the opaque digest is
// shown as a support reference.
export default function TenantAuthError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <AuthenticationTemplate
      footer={
        <Button variant="tertiary" href="/login">
          Back to sign in
        </Button>
      }
    >
      <ErrorState
        titleAs="h1"
        title="Something went wrong"
        description="We couldn't load this page. Try again in a moment."
        onRetry={retry}
        reference={error.digest}
      />
    </AuthenticationTemplate>
  );
}
