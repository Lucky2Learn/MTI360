"use client";

import { useRouter } from "next/navigation";

import { NavigationProvider } from "@/design-system/components";

import { ApplicationShell } from "./ApplicationShell";
import { getExperience, type ExperienceId } from "./experiences";
import { PublicSiteShell } from "./PublicSiteShell";

import type { ReactNode } from "react";

// ExperienceFrame (T00-08): picks and configures the shell for an experience.
// Experience layouts (server components) pass only the experience id; the
// configuration — which contains icon components — is resolved here on the
// client side of the boundary. It also connects React Aria links (Button
// href, menu links) to the Next.js router for client-side navigation.

export type ExperienceFrameProps = {
  experience: ExperienceId;
  children: ReactNode;
};

export function ExperienceFrame({
  experience: id,
  children,
}: ExperienceFrameProps) {
  const router = useRouter();
  const experience = getExperience(id);

  return (
    <NavigationProvider navigate={(href) => router.push(href)}>
      {experience.layout === "public" ? (
        <PublicSiteShell
          siteLabel={experience.label}
          homeHref={experience.basePath}
          navigation={experience.navigation}
          navigationLabel={experience.navigationLabel}
        >
          {children}
        </PublicSiteShell>
      ) : (
        <ApplicationShell
          experienceLabel={experience.label}
          homeHref={experience.basePath}
          navigation={experience.navigation}
          navigationLabel={experience.navigationLabel}
          sidebar={experience.sidebar}
          search={experience.search}
          account={experience.demo.account}
          notifications={
            experience.notifications ? experience.demo.notifications : undefined
          }
        >
          {children}
        </ApplicationShell>
      )}
    </NavigationProvider>
  );
}
