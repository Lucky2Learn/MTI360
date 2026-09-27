// Joins class names, skipping falsy values (T00-07, decision D4). Deliberately
// minimal: no clsx / class-variance-authority / tailwind-merge. Components use
// typed variant maps (Record<Variant, string>) instead of conditional merging,
// so conflicting utilities never need to be resolved at run time.

export type ClassValue = string | false | null | undefined;

export function cx(...values: ClassValue[]): string {
  return values.filter(Boolean).join(" ");
}

/**
 * Visible focus for React Aria components (data-focus-visible) and native
 * elements (:focus-visible): semantic focus-ring colour, width and offset from
 * the component tokens (WCAG 2.2 AA 2.4.7).
 */
export const focusRing =
  "outline-none data-focus-visible:outline-solid data-focus-visible:outline-(length:--focus-ring-width) data-focus-visible:outline-offset-(length:--focus-ring-offset) data-focus-visible:outline-focus-ring focus-visible:outline-solid focus-visible:outline-(length:--focus-ring-width) focus-visible:outline-offset-(length:--focus-ring-offset) focus-visible:outline-focus-ring";
