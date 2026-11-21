"use client";

import { useId } from "react";

import { Checkbox, RadioGroup } from "@/design-system/components";
import { ErrorIcon } from "@/design-system/icons";
import type { CampusScope, TenantCampusWire } from "@/lib/api/tenant-admin";

import { OWNER_SCOPE_CODE, OWNER_SCOPE_ERROR } from "./labels";

// Campus access for a member (02-C; ADMIN-05 invite, ADMIN-06 edit): all
// campuses, or a selection of the institute's campuses (T01-08: 1..100,
// validated by the API). The choices are the campuses the caller can see
// (GET /campuses); a selected campus outside them is kept and counted, never
// silently dropped.

export type CampusScopeValue = { scope: CampusScope; campusIds: string[] };

export function CampusScopeFields({
  campuses,
  value,
  onChange,
  errorMessage,
  scopeNote,
  isSelectedDisabled = false,
  scopeErrorMessage,
  isDisabled = false,
}: {
  campuses: TenantCampusWire[];
  value: CampusScopeValue;
  onChange: (value: CampusScopeValue) => void;
  /** An error about the chosen campuses. */
  errorMessage?: string;
  /** Shown under "Campus access", e.g. why selected campuses aren't available. */
  scopeNote?: string;
  /** "Selected campuses" can't be chosen (an owner keeps all campuses, ADR-0023). */
  isSelectedDisabled?: boolean;
  /** An error about the access choice itself (all or selected campuses). */
  scopeErrorMessage?: string;
  isDisabled?: boolean;
}) {
  const legendId = useId();
  const errorId = useId();
  const visible = new Set(campuses.map((campus) => campus.id));
  const hidden = value.campusIds.filter((id) => !visible.has(id)).length;

  const toggle = (id: string, selected: boolean) =>
    onChange({
      scope: "SELECTED",
      campusIds: selected
        ? [...value.campusIds, id]
        : value.campusIds.filter((item) => item !== id),
    });

  return (
    <div className="flex flex-col gap-4">
      <RadioGroup
        label="Campus access"
        options={[
          {
            value: "ALL",
            label: "All campuses",
            description: "Including campuses your institute adds later.",
          },
          {
            value: "SELECTED",
            label: "Selected campuses",
            description: "Only the campuses you choose.",
            isDisabled: isSelectedDisabled,
          },
        ]}
        description={scopeNote}
        errorMessage={scopeErrorMessage}
        isInvalid={Boolean(scopeErrorMessage)}
        value={value.scope}
        onChange={(scope) =>
          onChange({ scope: scope as CampusScope, campusIds: value.campusIds })
        }
        isDisabled={isDisabled}
      />
      {value.scope === "SELECTED" && (
        <fieldset
          className="flex min-w-0 flex-col gap-1"
          aria-labelledby={legendId}
          aria-describedby={errorMessage ? errorId : undefined}
          aria-invalid={errorMessage ? true : undefined}
        >
          <legend
            id={legendId}
            className="mb-1 text-body-sm font-medium text-text-primary"
          >
            Campuses
          </legend>
          {campuses.length === 0 ? (
            <p className="text-body-sm text-text-secondary">
              No campuses are available to you.
            </p>
          ) : (
            campuses.map((campus) => (
              <Checkbox
                key={campus.id}
                isSelected={value.campusIds.includes(campus.id)}
                onChange={(selected) => toggle(campus.id, selected)}
                isDisabled={isDisabled}
              >
                {`${campus.name} (${campus.code})`}
              </Checkbox>
            ))
          )}
          {hidden > 0 && (
            <p className="text-caption text-text-secondary">
              {`Also ${hidden} ${hidden === 1 ? "campus" : "campuses"} outside your access, kept as they are.`}
            </p>
          )}
          {errorMessage && (
            <p
              id={errorId}
              className="flex items-start gap-1 text-caption font-medium text-error-text"
            >
              <ErrorIcon aria-hidden="true" className="size-4 shrink-0" />
              {errorMessage}
            </p>
          )}
        </fieldset>
      )}
    </div>
  );
}

export const CAMPUS_MESSAGES: Record<string, string> = {
  required: "Choose at least one campus.",
  unknown: "Choose campuses of your institute.",
  not_allowed: "Leave campuses empty for all campuses.",
};

/** Field codes the API returns on `campus_scope` (ADR-0023). */
export const CAMPUS_SCOPE_MESSAGES: Record<string, string> = {
  [OWNER_SCOPE_CODE]: OWNER_SCOPE_ERROR,
};
