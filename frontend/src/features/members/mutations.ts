"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { toast } from "@/design-system/components";
import { ApiError } from "@/lib/api/errors";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { fieldCodes } from "../shared/forms";

// Member mutations (02-C; ADMIN-06 over the T01-08 API). Server
// authoritative, like the lead mutations: nothing changes on screen until
// the API answers, then the page re-renders from the server.
//
// Every refusal of the member API shares one code per status, and the server
// message is never shown, so each action names the reasons that apply to it:
// - 409 CONFLICT: a stale version, an invalid status change, the last active
//   owner (D8-4), a role already held or a disabled account → the action's
//   own warning, then the latest data;
// - 403 PERMISSION_DENIED: no permission, the caller's own membership (D8-4)
//   or a role with access the caller lacks (no escalation) → MEMBER_DENIED;
// - 404: the member (or role) is no longer visible → the latest data;
// - 422: field codes for the dialog.

export type MemberOutcome =
  | { kind: "done" }
  | { kind: "fields"; fields: Record<string, string> }
  | { kind: "feedback"; feedback: FormFeedback };

export const MEMBER_DENIED: FormFeedback = {
  tone: "error",
  title: "You can't make this change",
  body: "It needs access you don't have, or it affects your own membership. Ask another administrator.",
};

const FALLBACK: FormFeedback = {
  tone: "error",
  title: "Something went wrong",
  body: "Something went wrong. Try again in a moment.",
};

export type MemberCall = {
  path: `/${string}`;
  method?: "POST" | "PUT" | "DELETE";
  body?: unknown;
  /** Toast after the API accepted the change. */
  success: string;
  /** Warning when the API refused with 409 (the latest data is then shown). */
  conflict: string;
};

export function useMemberMutation() {
  const router = useRouter();
  const { request } = useTenantSession();

  return useCallback(
    async ({
      path,
      method = "POST",
      body,
      success,
      conflict,
    }: MemberCall): Promise<MemberOutcome> => {
      try {
        await request(path, body === undefined ? { method } : { method, body });
        toast.success(success);
        router.refresh();
        return { kind: "done" };
      } catch (error) {
        if (error instanceof ApiError && error.code === "CONFLICT") {
          toast.warning(conflict);
          router.refresh();
          return { kind: "done" };
        }
        if (error instanceof ApiError && error.code === "NOT_FOUND") {
          toast.info(
            "This is no longer available. The latest details are shown.",
          );
          router.refresh();
          return { kind: "done" };
        }
        if (error instanceof ApiError && error.code === "PERMISSION_DENIED") {
          return { kind: "feedback", feedback: MEMBER_DENIED };
        }
        const fields = fieldCodes(error);
        if (Object.keys(fields).length > 0) return { kind: "fields", fields };
        return { kind: "feedback", feedback: formFeedback(error) ?? FALLBACK };
      }
    },
    [request, router],
  );
}

/** Confirm-only actions (no form): a refusal becomes one error toast. */
export function toastFeedback(feedback: FormFeedback): void {
  const show = feedback.tone === "warning" ? toast.warning : toast.error;
  show(feedback.title, feedback.body ? { description: feedback.body } : {});
}
