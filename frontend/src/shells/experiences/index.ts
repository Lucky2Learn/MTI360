import {
  findTrail,
  flattenNavigation,
  isCurrentPage,
  normalizePath,
  type NavItem,
} from "../navigation";

import { platformExperience } from "./platform";
import { publicSiteExperience } from "./public-site";
import { studentExperience } from "./student";
import { tenantExperience } from "./tenant";
import { EXPERIENCE, type ExperienceConfig, type ExperienceId } from "./types";

export * from "./types";

// Experience registry and route resolution (T00-08). The placeholder pages of
// each experience are exactly the pages in its navigation configuration;
// any other path below the boundary is a 404 (dynamicParams = false).

export const EXPERIENCES: Record<ExperienceId, ExperienceConfig> = {
  [EXPERIENCE.PLATFORM]: platformExperience,
  [EXPERIENCE.TENANT]: tenantExperience,
  [EXPERIENCE.STUDENT]: studentExperience,
  [EXPERIENCE.PUBLIC_SITE]: publicSiteExperience,
};

export function getExperience(id: ExperienceId): ExperienceConfig {
  return EXPERIENCES[id];
}

export type ExperiencePage = {
  experience: ExperienceConfig;
  /** The navigation item for this path. */
  item: NavItem;
  /** Ancestors and the item itself (for breadcrumbs). */
  trail: NavItem[];
  isHome: boolean;
};

function pathFor(experience: ExperienceConfig, slug: string[] = []): string {
  return normalizePath([experience.basePath, ...slug].join("/"));
}

/** The configured page for a catch-all slug, or null (→ 404). */
export function resolveExperiencePage(
  id: ExperienceId,
  slug?: string[],
): ExperiencePage | null {
  const experience = getExperience(id);
  const pathname = pathFor(experience, slug);
  const trail = findTrail(experience.navigation, pathname);
  const item = trail.at(-1);
  if (!item || !isCurrentPage(item, pathname)) return null;
  return {
    experience,
    item,
    trail,
    isHome: pathname === normalizePath(experience.basePath),
  };
}

/** Static params for the experience's optional catch-all route. */
export function experienceStaticParams(id: ExperienceId): { slug: string[] }[] {
  const experience = getExperience(id);
  const base = normalizePath(experience.basePath);
  return flattenNavigation(experience.navigation).map((item) => ({
    slug: normalizePath(item.href)
      .slice(base.length)
      .split("/")
      .filter(Boolean),
  }));
}
