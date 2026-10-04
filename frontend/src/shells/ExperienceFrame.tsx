"use client";

import { useRouter } from "next/navigation";

import { NavigationProvider } from "@/design-system/components";

import { ApplicationShell } from "./ApplicationShell";
import { getExperience, type ExperienceId } from "./experiences";
import { PublicSiteShell } from "./PublicSiteShell";

import type { Navigation } from "./navigation";
import type { ShellAccount, UserMenuSession } from "./UserMenu";
import type { ReactNode } from "react";

// ExperienceFrame (T00-08): picks and configures the shell for an experience.
// Experience layouts (server components) pass only the experience id; the
// configuration — which contains icon components — is resolved here on the
// client side of the boundary. It also connects React Aria links (Button
// href, menu links) to the Next.js router for client-side navigation.

/**
 * Values that come from a signed-in session (T01-09A, tenant experience):
 * the permission-filtered navigation, the account and the session controls.
 * Without it the experience's configuration and demo account are used.
 */
export type ExperienceSession = {
  navigation: Navigation;
  account: ShellAccount;
  headerContext?: ReactNode;
  accountSession?: UserMenuSession;
};

export type ExperienceFrameProps = {
  experience: ExperienceId;
  session?: ExperienceSession;
  children: ReactNode;
};

export function ExperienceFrame({
  experience: id,
  session,
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
          navigation={session?.navigation ?? experience.navigation}
          navigationLabel={experience.navigationLabel}
          sidebar={experience.sidebar}
          search={experience.search}
          account={session?.account ?? experience.demo.account}
          notifications={
            experience.notifications ? experience.demo.notifications : undefined
          }
          headerContext={session?.headerContext}
          accountSession={session?.accountSession}
        >
          {children}
        </ApplicationShell>
      )}
    </NavigationProvider>
  );
}
