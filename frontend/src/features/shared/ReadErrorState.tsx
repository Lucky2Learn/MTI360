"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { ErrorState } from "@/design-system/components";

// The failed-load state of a business page (Phase 02-1; blueprint §21): fixed
// copy, the support reference (the request ID) and a retry that re-renders
// the page on the server. Never the server's message.

export function ReadErrorState({
  title = "This page couldn't be loaded",
  reference,
}: {
  title?: string;
  reference: string | null;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <ErrorState
      title={title}
      description="Something went wrong on our side. Try again in a moment."
      reference={reference ?? undefined}
      onRetry={() => startTransition(() => router.refresh())}
      isRetrying={pending}
    />
  );
}
