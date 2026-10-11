"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { toast } from "@/design-system/components";
import { ApiError } from "@/lib/api/errors";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { fieldCodes } from "../shared/forms";

// Finance-lite mutations from forms and dialogs (Phase 02-5; ADR-0022,
// addendum R1-R3). Server authoritative: nothing changes on screen until the
// API answers, then the page re-renders from the server. Two different 409s:
// a stale `version` shows the latest data (as everywhere), but a reused
// idempotency key means the same form was already submitted with other
// details — the form stays as it is and explains, and nothing is resent.
// Validation codes stay with the form; server messages are never shown.

export type FinanceOutcome<T = unknown> =
  | { kind: "done"; data: T }
  | { kind: "stale" }
  | { kind: "fields"; fields: Record<string, string> }
  | { kind: "feedback"; feedback: FormFeedback };

export const FALLBACK: FormFeedback = {
  tone: "error",
  title: "Something went wrong",
  body: "Something went wrong. Try again in a moment.",
};

export const KEY_REUSED: FormFeedback = {
  tone: "warning",
  title: "This form was already sent with different details",
  body: "Reload the page to see whether it was saved before you change anything.",
};

/** True for 409 `idempotency_key_reused` (addendum R3). */
export function isKeyReused(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    error.code === "CONFLICT" &&
    error.fieldCode("idempotency_key") === "idempotency_key_reused"
  );
}

/** `field → code` of a 409 that carries field details (e.g. live_invoice_exists). */
function conflictFields(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || error.code !== "CONFLICT") return {};
  const fields: Record<string, string> = {};
  for (const detail of error.details) {
    if (detail.field && !(detail.field in fields)) {
      fields[detail.field] = detail.code;
    }
  }
  return fields;
}

export function useFinanceMutation(noun: string) {
  const router = useRouter();
  const { request } = useTenantSession();

  return useCallback(
    async <T = unknown>(
      path: `/${string}`,
      body: unknown,
      success: string | null,
    ): Promise<FinanceOutcome<T>> => {
      try {
        const data = await request<T>(path, { method: "POST", body });
        if (success) toast.success(success);
        router.refresh();
        return { kind: "done", data };
      } catch (error) {
        if (isKeyReused(error))
          return { kind: "feedback", feedback: KEY_REUSED };
        const conflict = conflictFields(error);
        if (Object.keys(conflict).length > 0) {
          return { kind: "fields", fields: conflict };
        }
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
        const fields = fieldCodes(error);
        if (Object.keys(fields).length > 0) return { kind: "fields", fields };
        return { kind: "feedback", feedback: formFeedback(error) ?? FALLBACK };
      }
    },
    [noun, request, router],
  );
}

/** One idempotency key per form, created in the browser (addendum R3). */
export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}
