"use client";

import { useId } from "react";

import { Checkbox } from "@/design-system/components";
import { ErrorIcon } from "@/design-system/icons";
import type { TenantRoleWire } from "@/lib/api/tenant-admin";

import { grantable } from "./labels";

// Initial roles of an invitation (02-C; ADMIN-05). A role holding access the
// caller doesn't have is shown disabled and says why (the no-escalation rule
// as a hint; the API decides). Roles are optional: they can be added later.

export const NOT_GRANTABLE = "Includes access you don't have.";

export function RoleChoices({
  roles,
  permissions,
  selected,
  onChange,
  errorMessage,
  isDisabled = false,
}: {
  roles: TenantRoleWire[];
  permissions: ReadonlySet<string>;
  selected: string[];
  onChange: (ids: string[]) => void;
  errorMessage?: string;
  isDisabled?: boolean;
}) {
  const legendId = useId();
  const hintId = useId();
  const errorId = useId();
  return (
    <fieldset
      className="flex min-w-0 flex-col gap-1"
      aria-labelledby={legendId}
      aria-describedby={errorMessage ? `${hintId} ${errorId}` : hintId}
      aria-invalid={errorMessage ? true : undefined}
    >
      <legend
        id={legendId}
        className="text-body-sm font-medium text-text-primary"
      >
        Roles
      </legend>
      <p id={hintId} className="mb-1 text-caption text-text-secondary">
        Optional. Roles decide what the member can do; you can change them
        later.
      </p>
      {roles.length === 0 ? (
        <p className="text-body-sm text-text-secondary">
          No roles are available.
        </p>
      ) : (
        roles.map((role) => {
          const allowed = grantable(role, permissions);
          return (
            <Checkbox
              key={role.id}
              isSelected={selected.includes(role.id)}
              onChange={(on) =>
                onChange(
                  on
                    ? [...selected, role.id]
                    : selected.filter((id) => id !== role.id),
                )
              }
              isDisabled={isDisabled || !allowed}
              description={allowed ? undefined : NOT_GRANTABLE}
            >
              {role.name}
            </Checkbox>
          );
        })
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
  );
}
