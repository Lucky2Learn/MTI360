import type {
  CampusWire,
  InstituteWire,
  SessionStatus,
  SessionWire,
} from "@/lib/api/types";

// Client session state (T01-05 UI contract §5). Derived from ONE session
// response and replaced as a whole on every re-read — never merged with an
// earlier one, never persisted (no localStorage, sessionStorage or readable
// cookie), never taken from a URL. It drives UX only; the API authorizes
// every request (CLAUDE.md §10).

export type Institute = { id: string; name: string; isTrial: boolean };
export type Campus = { id: string; name: string; code: string };
export type Role = { name: string; isSystem: boolean };

export type Session = {
  status: SessionStatus;
  user: { displayName: string; email: string };
  activeInstitute: Institute | null;
  institutes: Institute[];
  activeCampus: Campus | null;
  campusOptions: Campus[];
  allCampusesAllowed: boolean;
  campusSelectionRequired: boolean;
  /** Opaque permission codes; compared for equality only (no wildcards). */
  permissions: ReadonlySet<string>;
  /** Display only: never used to decide anything (no role gating). */
  roles: Role[];
  /** In memory only; sent as X-CSRF-Token on unsafe requests. */
  csrfToken: string;
};

const collator = new Intl.Collator(undefined, { sensitivity: "base" });
const byName = (a: { name: string }, b: { name: string }) =>
  collator.compare(a.name, b.name);

const toInstitute = (item: InstituteWire): Institute => ({
  id: item.id,
  name: item.name,
  isTrial: item.is_trial,
});

const toCampus = (item: CampusWire): Campus => ({
  id: item.id,
  name: item.name,
  code: item.code,
});

export function toSession(wire: SessionWire): Session {
  return {
    status: wire.status,
    user: { displayName: wire.user.display_name, email: wire.user.email },
    activeInstitute: wire.active_institute
      ? toInstitute(wire.active_institute)
      : null,
    institutes: wire.institutes.map(toInstitute).sort(byName),
    activeCampus: wire.active_campus ? toCampus(wire.active_campus) : null,
    campusOptions: wire.campus_options.map(toCampus).sort(byName),
    allCampusesAllowed: wire.all_campuses_allowed,
    campusSelectionRequired: wire.campus_selection_required,
    permissions: new Set(wire.permissions),
    roles: wire.roles.map((role) => ({
      name: role.name,
      isSystem: role.is_system,
    })),
    csrfToken: wire.csrf_token,
  };
}

/** Two-letter decorative monogram from the display name. */
export function monogram(displayName: string): string {
  const letters = displayName
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word[0]!.toUpperCase());
  if (letters.length === 0) return "?";
  return letters.length === 1 ? letters[0]! : `${letters[0]}${letters.at(-1)}`;
}
