"use client";

import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { ToastRegion } from "@/design-system/components";
import { cx } from "@/design-system/lib/cx";

import { AppHeader } from "./AppHeader";
import { AppSidebar, sidebarOffset, type SidebarMode } from "./AppSidebar";
import { CommandSearch } from "./CommandSearch";
import { MobileNavigation } from "./MobileNavigation";
import {
  NotificationCenter,
  type ShellNotification,
} from "./NotificationCenter";
import { MAIN_CONTENT_ID, SkipNavigation } from "./SkipNavigation";
import { UserMenu, type ShellAccount } from "./UserMenu";

import type { Navigation } from "./navigation";

// ApplicationShell (T00-08): composition for the Platform, Tenant and Student
// experiences: skip link → header (navigation drawer trigger below desktop)
// → sidebar → main content. Structural only: it does not authenticate,
// authorize or resolve a tenant; the navigation it receives is configuration
// that later phases filter server-side. The shell mounts the application's
// single global ToastRegion, so any code inside it can call toast.*().

export type ApplicationShellProps = {
  /** Name of the experience, e.g. "Platform Administration". */
  experienceLabel: string;
  homeHref: string;
  navigation: Navigation;
  /** Accessible name of the navigation landmark. */
  navigationLabel: string;
  sidebar?: SidebarMode;
  account: ShellAccount;
  /** Show the page search entry point (Ctrl+K). */
  search?: boolean;
  /** Notification centre items; omit to hide the notification entry point. */
  notifications?: ShellNotification[];
  children: ReactNode;
};

export function ApplicationShell({
  experienceLabel,
  homeHref,
  navigation,
  navigationLabel,
  sidebar = "collapsible",
  account,
  search = false,
  notifications,
  children,
}: ApplicationShellProps) {
  const pathname = usePathname() ?? homeHref;
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex min-h-dvh flex-col">
      <SkipNavigation />
      <AppHeader
        experienceLabel={experienceLabel}
        homeHref={homeHref}
        navigationTrigger={
          <MobileNavigation
            experienceLabel={experienceLabel}
            navigationLabel={navigationLabel}
            navigation={navigation}
            pathname={pathname}
          />
        }
        actions={
          <>
            {search && (
              <CommandSearch
                experienceLabel={experienceLabel}
                navigation={navigation}
              />
            )}
            {notifications && (
              <NotificationCenter notifications={notifications} />
            )}
            <UserMenu account={account} />
          </>
        }
      />
      <AppSidebar
        navigationLabel={navigationLabel}
        navigation={navigation}
        pathname={pathname}
        mode={sidebar}
        collapsed={collapsed}
        onCollapsedChange={setCollapsed}
      />
      <main
        id={MAIN_CONTENT_ID}
        tabIndex={-1}
        className={cx(
          "flex min-w-0 flex-1 flex-col outline-none",
          sidebarOffset(sidebar, collapsed),
        )}
      >
        {children}
      </main>
      <ToastRegion />
    </div>
  );
}
