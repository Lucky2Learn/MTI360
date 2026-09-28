"use client";

import { ShellError } from "@/shells";

// Route error boundary (T00-08): a user-safe message with retry. The error
// message is never rendered; only the opaque digest is shown as a reference
// for support to find the server log entry.
export default function PlatformError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <ShellError onRetry={retry} homeHref="/platform" reference={error.digest} />
  );
}
