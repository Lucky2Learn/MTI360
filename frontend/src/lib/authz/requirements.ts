// Permission requirements (T01-05 UI contract §6, §12). Advisory only: they
// decide what the UI shows and which page state renders. The API authorizes
// every request regardless (CLAUDE.md §10; T01-05 §3, S1).
//
// Every tenant navigation item and page declares exactly one requirement:
// - { permission: "<code>" }: shown and reachable with that code;
// - "ALWAYS": any member with an active institute (Dashboard only);
// - "UNRELEASED": no permission exists yet; visible in development builds
//   only (T01-05 §6), hidden and unreachable everywhere else.
// There is deliberately no role-based requirement (no hasRole).

export type Requirement =
  { readonly permission: string } | "ALWAYS" | "UNRELEASED";

export const ALWAYS = "ALWAYS" satisfies Requirement;
export const UNRELEASED = "UNRELEASED" satisfies Requirement;

export const permission = (code: string): Requirement => ({ permission: code });

/** UNRELEASED pages exist only in development (T01-05 UI contract §6). */
export function unreleasedVisible(appEnv: string): boolean {
  return appEnv === "development";
}

export type Permissions = ReadonlySet<string> | readonly string[];

function has(permissions: Permissions, code: string): boolean {
  return Array.isArray(permissions)
    ? permissions.includes(code)
    : (permissions as ReadonlySet<string>).has(code);
}

/** Exact match; unknown codes are false; no wildcard or prefix matching. */
export function can(permissions: Permissions, code: string): boolean {
  return typeof code === "string" && code.length > 0 && has(permissions, code);
}

export function canAny(permissions: Permissions, codes: readonly string[]) {
  return codes.some((code) => can(permissions, code));
}

export function canAll(permissions: Permissions, codes: readonly string[]) {
  return codes.length > 0 && codes.every((code) => can(permissions, code));
}

export type RequirementContext = {
  permissions: Permissions;
  /** Whether UNRELEASED pages exist in this environment. */
  showUnreleased: boolean;
};

/** Whether `requirement` is met. A missing requirement is never met. */
export function meets(
  requirement: Requirement | undefined,
  { permissions, showUnreleased }: RequirementContext,
): boolean {
  if (requirement === undefined) return false;
  if (requirement === ALWAYS) return true;
  if (requirement === UNRELEASED) return showUnreleased;
  return can(permissions, requirement.permission);
}
