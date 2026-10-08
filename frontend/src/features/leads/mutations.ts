"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { toast } from "@/design-system/components";
import { ApiError } from "@/lib/api/errors";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { fieldCodes } from "../shared/forms";

// Lead mutations from dialogs (Phase 02-1; blueprint §21-§22). Server
// authoritative: nothing changes on screen until the API answers, then the
// page re-renders from the server (router.refresh()). A stale version (409)
// or a lead that is no longer visible (404) closes the dialog with a toast and
// shows the current data; validation errors stay in the dialog.

export type MutationOutcome =
  | { kind: "done" }
  | { kind: "fields"; fields: Record<string, string> }
  | { kind: "feedback"; feedback: FormFeedback };

const FALLBACK: FormFeedback = {
  tone: "error",
  title: "Something went wrong",
  body: "Something went wrong. Try again in a moment.",
};

export function useLeadMutation() {
  const router = useRouter();
  const { request } = useTenantSession();

  return useCallback(
    async (
      path: `/${string}`,
      body: unknown,
      success: string,
      method: "POST" | "PATCH" = "POST",
    ): Promise<MutationOutcome> => {
      try {
        await request(path, { method, body });
        toast.success(success);
        router.refresh();
        return { kind: "done" };
      } catch (error) {
        if (error instanceof ApiError && error.code === "CONFLICT") {
          toast.warning("This lead changed — the latest version is shown.");
          router.refresh();
          return { kind: "done" };
        }
        if (error instanceof ApiError && error.code === "NOT_FOUND") {
          toast.info("This lead is no longer available.");
          router.refresh();
          return { kind: "done" };
        }
        const fields = fieldCodes(error);
        if (Object.keys(fields).length > 0) return { kind: "fields", fields };
        return { kind: "feedback", feedback: formFeedback(error) ?? FALLBACK };
      }
    },
    [request, router],
  );
}
