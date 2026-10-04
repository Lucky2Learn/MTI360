"use client";

import { useTenantSession } from "@/lib/session/SessionProvider";

import type { ReactNode } from "react";

// PermissionGate (T01-05 UI contract §12; DESIGN-SYSTEM.md §69). UX only:
// renders its children when the current session has the permission and
// NOTHING otherwise (§9: missing permission → hide; no disabled mode, no
// fallback in T01). Hiding is never security — the API refuses the request
// anyway, and the UI handles that refusal (RESOURCE-01).

export type PermissionGateProps = {
  /** Exact permission code, e.g. "member.invite". Never a role name. */
  permission: string;
  children: ReactNode;
};

export function PermissionGate({ permission, children }: PermissionGateProps) {
  const { can } = useTenantSession();
  return can(permission) ? children : null;
}
