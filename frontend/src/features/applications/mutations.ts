"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { toast } from "@/design-system/components";
import { ApiError } from "@/lib/api/errors";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { fieldCodes } from "../shared/forms";

// Application and document mutations from dialogs and wizard steps (Phase
// 02-2). Server authoritative, as for leads: nothing changes on screen until
// the API answers, then the page re-renders from the server. A stale version
// (409) or a record that is no longer visible (404) shows the current data
// with a toast; validation codes stay with the form; server messages are
// never displayed.

export type Outcome<T = unknown> =
  | { kind: "done"; data: T }
  | { kind: "stale" }
  | { kind: "fields"; fields: Record<string, string> }
  | { kind: "feedback"; feedback: FormFeedback };

export const FALLBACK: FormFeedback = {
  tone: "error",
  title: "Something went wrong",
  body: "Something went wrong. Try again in a moment.",
};

export function useRecordMutation(noun: string) {
  const router = useRouter();
  const { request } = useTenantSession();

  return useCallback(
    async <T = unknown>(
      path: `/${string}`,
      body: unknown,
      success: string | null,
      method: "POST" | "PATCH" = "POST",
    ): Promise<Outcome<T>> => {
      try {
        const data = await request<T>(path, { method, body });
        if (success) toast.success(success);
        router.refresh();
        return { kind: "done", data };
      } catch (error) {
        if (error instanceof ApiError && error.code === "CONFLICT") {
          toast.warning(`This ${noun} changed — the latest version is shown.`);
          router.refresh();
          return { kind: "stale" };
        }
        if (error instanceof ApiError && error.code === "NOT_FOUND") {
          toast.info(`This ${noun} is no longer available.`);
          router.refresh();
          return { kind: "stale" };
        }
        if (error instanceof ApiError && error.code === "PAYLOAD_TOO_LARGE") {
          return { kind: "fields", fields: { file: "file_too_large" } };
        }
        const fields = fieldCodes(error);
        if (Object.keys(fields).length > 0) return { kind: "fields", fields };
        return { kind: "feedback", feedback: formFeedback(error) ?? FALLBACK };
      }
    },
    [noun, request, router],
  );
}
