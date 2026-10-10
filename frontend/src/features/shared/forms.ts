import { ApiError } from "@/lib/api/errors";

// Form helpers shared by business forms (Phase 02-1; CLAUDE.md §34).

/** Moves focus to the first invalid control of `form` (after the next paint). */
export function focusFirstInvalid(form: HTMLElement | null): void {
  if (!form) return;
  requestAnimationFrame(() => {
    const target =
      form.querySelector<HTMLElement>('[aria-invalid="true"]') ??
      form.querySelector<HTMLElement>(
        "[data-invalid] input, [data-invalid] textarea, [data-invalid] button",
      );
    target?.focus();
  });
}

/**
 * Field errors of a 422 response, as `field → detail code`. Screens map codes
 * to their own copy; server messages are never shown.
 */
export function fieldCodes(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || error.code !== "VALIDATION_ERROR") {
    return {};
  }
  const result: Record<string, string> = {};
  for (const detail of error.details) {
    if (detail.field && !(detail.field in result)) {
      result[detail.field] = detail.code;
    }
  }
  return result;
}
