"use client";

import { useState } from "react";

import { Drawer, IconButton } from "@/design-system/components";
import { MenuIcon } from "@/design-system/icons";

import { AppNavigation } from "./AppNavigation";

import type { Navigation } from "./navigation";

// MobileNavigation (T00-08): the experience navigation in the T00-07C Drawer
// for mobile and tablet (hidden from the desktop breakpoint, where the sidebar
// is expanded). Drawer semantics: labelled modal dialog, focus moves in and is
// trapped, Escape and the scrim close it, focus returns to the trigger. The
// drawer also closes when a link is followed.

export type MobileNavigationProps = {
  experienceLabel: string;
  navigationLabel: string;
  navigation: Navigation;
  pathname: string;
};

export function MobileNavigation({
  experienceLabel,
  navigationLabel,
  navigation,
  pathname,
}: MobileNavigationProps) {
  const [isOpen, setOpen] = useState(false);
  return (
    <span className="flex desktop:hidden">
      <Drawer
        side="left"
        size="sm"
        title={experienceLabel}
        closeLabel="Close navigation"
        isOpen={isOpen}
        onOpenChange={setOpen}
        trigger={<IconButton label="Open navigation" icon={MenuIcon} />}
      >
        <AppNavigation
          label={navigationLabel}
          navigation={navigation}
          pathname={pathname}
          display="full"
          onNavigate={() => setOpen(false)}
        />
      </Drawer>
    </span>
  );
}
