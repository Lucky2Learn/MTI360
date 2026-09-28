"use client";

import { IconButton } from "@/design-system/components";
import { CollapseSidebarIcon, ExpandSidebarIcon } from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

import { AppNavigation } from "./AppNavigation";

import type { Navigation } from "./navigation";

// AppSidebar (T00-08): persistent navigation column below the header.
// - "collapsible": icon rail on tablet; expanded on desktop with a
//   collapse/expand control (Platform, Tenant);
// - "fixed": desktop only, always expanded (Student Portal); tablet and mobile
//   use the navigation drawer.
// Below its breakpoint the sidebar is display:none, so it leaves the
// accessibility tree and the navigation drawer provides the same links.

export type SidebarMode = "collapsible" | "fixed";

function sidebarWidth(mode: SidebarMode, collapsed: boolean): string {
  if (mode === "fixed") return "desktop:w-64";
  return collapsed ? "tablet:w-16" : "tablet:w-16 desktop:w-64";
}

/** Left offset of the main column so content never sits under the sidebar. */
export function sidebarOffset(mode: SidebarMode, collapsed: boolean): string {
  if (mode === "fixed") return "desktop:pl-64";
  return collapsed ? "tablet:pl-16" : "tablet:pl-16 desktop:pl-64";
}

export type AppSidebarProps = {
  navigationLabel: string;
  navigation: Navigation;
  pathname: string;
  mode?: SidebarMode;
  collapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
};

export function AppSidebar({
  navigationLabel,
  navigation,
  pathname,
  mode = "collapsible",
  collapsed = false,
  onCollapsedChange,
}: AppSidebarProps) {
  const isCollapsed = mode === "collapsible" && collapsed;
  return (
    <div
      data-sidebar={mode}
      data-collapsed={isCollapsed ? "" : undefined}
      className={cx(
        "fixed top-16 bottom-0 left-0 z-(--z-sticky) hidden flex-col border-r border-border-subtle bg-surface-primary",
        mode === "fixed" ? "desktop:flex" : "tablet:flex",
        sidebarWidth(mode, collapsed),
      )}
    >
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        <AppNavigation
          label={navigationLabel}
          navigation={navigation}
          pathname={pathname}
          display={mode === "fixed" ? "full" : isCollapsed ? "rail" : "auto"}
        />
      </div>
      {mode === "collapsible" && (
        <div className="hidden justify-end border-t border-border-subtle p-2 desktop:flex">
          <IconButton
            label={isCollapsed ? "Expand navigation" : "Collapse navigation"}
            icon={isCollapsed ? ExpandSidebarIcon : CollapseSidebarIcon}
            onPress={() => onCollapsedChange?.(!isCollapsed)}
          />
        </div>
      )}
    </div>
  );
}
