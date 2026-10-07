import { useId, type ReactNode } from "react";

import { cx } from "@/design-system/lib/cx";

// SecretValue and CodeList (T01-09B, design-system extension): one-time
// security values — an authenticator setup key, recovery codes — shown in the
// system monospace (`font-mono`, design-tokens.md D6) on a quiet surface,
// with semantic tokens in Light and Dark. They render only what they are
// given: the caller owns the value, keeps it in memory and drops it. Text is
// selectable and wraps (never clipped at 390px). No copy-on-render, no
// storage, no logging.

const surface =
  "rounded-md border border-border-subtle bg-surface-secondary font-mono text-text-primary";

/** Groups `value` in blocks of `size` characters separated by spaces. */
export function groupCharacters(value: string, size = 4): string {
  const compact = value.replace(/\s+/g, "");
  const groups: string[] = [];
  for (let index = 0; index < compact.length; index += size) {
    groups.push(compact.slice(index, index + size));
  }
  return groups.join(" ");
}

export type SecretValueProps = {
  /** Visible label, e.g. "Setup key". */
  label: string;
  value: string;
  /** Characters per group (readability); 0 shows the value unchanged. */
  groupSize?: number;
  /** Actions below the value, e.g. a CopyButton. */
  actions?: ReactNode;
};

export function SecretValue({
  label,
  value,
  groupSize = 4,
  actions,
}: SecretValueProps) {
  const labelId = useId();
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <p id={labelId} className="text-body-sm font-semibold text-text-primary">
        {label}
      </p>
      <p
        aria-labelledby={labelId}
        className={cx(
          surface,
          "px-3 py-2 text-body tracking-wide break-all select-all",
        )}
      >
        {groupSize > 0 ? groupCharacters(value, groupSize) : value}
      </p>
      {actions}
    </div>
  );
}

export type CodeListProps = {
  /** Accessible name of the list, e.g. "Recovery codes". */
  label: string;
  codes: readonly string[];
};

/** An ordered list of one-time codes, two columns from tablet. */
export function CodeList({ label, codes }: CodeListProps) {
  return (
    <ol
      aria-label={label}
      className={cx(
        surface,
        "grid list-inside list-decimal grid-cols-1 gap-x-6 gap-y-1 px-4 py-3 text-body tablet:grid-cols-2",
        "marker:text-text-muted",
      )}
    >
      {codes.map((code) => (
        <li key={code} className="break-all">
          {code}
        </li>
      ))}
    </ol>
  );
}
