"use client";

import { useEffect, useState } from "react";

import { Select } from "@/design-system/components";

// MemberPicker (Phase 02-1; blueprint §10, §28): choose a team member from a
// feature endpoint that returns only eligible members (lead owner and
// follow-up assignee now; application owner in 02-2). It never lists members
// through member.read: the feature's own permission governs the list. While
// loading or when the list fails, only the current choice and "Unassigned"
// (when allowed) are offered; the server re-checks eligibility on save.

export type MemberOption = { id: string; label: string };

export const UNASSIGNED = "unassigned";

export type MemberPickerProps = {
  label: string;
  /** Loads the eligible members (re-run when `loadKey` changes). */
  load: () => Promise<MemberOption[]>;
  loadKey: string;
  value: string | null;
  onChange: (membershipId: string | null) => void;
  /** Offer "Unassigned" (null). */
  allowUnassigned?: boolean;
  /** The current choice, shown even if it is no longer eligible. */
  current?: MemberOption | null;
  description?: string;
  errorMessage?: string;
};

export function MemberPicker({
  label,
  load,
  loadKey,
  value,
  onChange,
  allowUnassigned = false,
  current,
  description,
  errorMessage,
}: MemberPickerProps) {
  const [loaded, setLoaded] = useState<{
    key: string;
    members: MemberOption[] | null;
    failed: boolean;
  } | null>(null);

  useEffect(() => {
    let active = true;
    load().then(
      (items) =>
        active && setLoaded({ key: loadKey, members: items, failed: false }),
      () => active && setLoaded({ key: loadKey, members: null, failed: true }),
    );
    return () => {
      active = false;
    };
    // `load` is recreated by callers on every render; `loadKey` names its inputs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadKey]);

  const latest = loaded?.key === loadKey ? loaded : null;
  const members = latest?.members ?? null;
  const failed = latest?.failed ?? false;

  const options: MemberOption[] = [
    ...(allowUnassigned ? [{ id: UNASSIGNED, label: "Unassigned" }] : []),
    ...(current && !members?.some((m) => m.id === current.id) ? [current] : []),
    ...(members ?? []),
  ];
  const help = failed
    ? "The team list couldn't be loaded. Try again later."
    : members === null
      ? "Loading the team…"
      : description;

  return (
    <Select
      label={label}
      options={options}
      value={value ?? (allowUnassigned ? UNASSIGNED : null)}
      onChange={(id) => onChange(id === UNASSIGNED ? null : id)}
      description={help}
      isInvalid={Boolean(errorMessage)}
      errorMessage={errorMessage}
    />
  );
}
