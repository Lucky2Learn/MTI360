import type { SidebarMode } from "../AppSidebar";
import type { Navigation } from "../navigation";
import type { ShellNotification } from "../NotificationCenter";
import type { PageWidth } from "../PageContainer";
import type { ShellAccount } from "../UserMenu";

// Experience framework (T00-08; CLAUDE.md §4). MTI 360 has four product
// experiences with separate route boundaries, shells and navigation. This is
// a STRUCTURAL boundary only: it does not authenticate, authorize, resolve a
// tenant or read any identifier from the browser. Later phases enforce access
// server-side at these boundaries (ADR-0004, ADR-0005) and replace the demo
// account/notification data with real, server-provided data.
//
// The MTI 360 marketing website is NOT an experience (ADR-0003, INC-26).

export const EXPERIENCE = {
  PLATFORM: "platform",
  TENANT: "tenant",
  STUDENT: "student",
  PUBLIC_SITE: "public-site",
} as const;

export type ExperienceId = (typeof EXPERIENCE)[keyof typeof EXPERIENCE];

type ExperienceBase = {
  id: ExperienceId;
  /** Human-readable name, e.g. "Platform Administration". */
  label: string;
  /** Route boundary, e.g. "/platform". Every navigation href lives below it. */
  basePath: string;
  /** Accessible name of the navigation landmark. */
  navigationLabel: string;
  navigation: Navigation;
  pageWidth: PageWidth;
};

/** Signed-in application experiences (Platform, Tenant, Student). */
export type ApplicationExperience = ExperienceBase & {
  layout: "application";
  sidebar: SidebarMode;
  search: boolean;
  notifications: boolean;
  /** Development placeholders until authentication and data exist. */
  demo: { account: ShellAccount; notifications: ShellNotification[] };
};

/** Public, unauthenticated experience (Tenant Public Website). */
export type PublicExperience = ExperienceBase & {
  layout: "public";
};

export type ExperienceConfig = ApplicationExperience | PublicExperience;
