"use client";

import { Button, ErrorState } from "@/design-system/components";
import { AuthenticationTemplate } from "@/design-system/templates/AuthenticationTemplate";
import { PLATFORM_CONTEXT } from "@/features/identity/realm";

// Error boundary of the platform authentication screens (T01-09B): fixed,
// user-safe text with retry; never the error message (CLAUDE.md §37). Only
// the opaque digest is shown as a support reference.
export default function PlatformAuthError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <AuthenticationTemplate
      context={PLATFORM_CONTEXT}
      footer={
        <Button variant="tertiary" href="/platform/login">
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
