"use client";

import { useState } from "react";

import {
  Button,
  Dialog,
  DropdownMenu,
  toast,
  type MenuEntry,
} from "@/design-system/components";
import {
  HelpIcon,
  PreferencesIcon,
  ProfileIcon,
  SignOutIcon,
} from "@/design-system/icons";
import { ThemeSelector } from "@/design-system/theme/ThemeSelector";

// UserMenu (T00-08): account entry point built on the T00-07C DropdownMenu.
// Structural only — there is no authentication yet (Phase 01): Profile, Help
// and Sign out explain that they are not available; nothing is invalidated
// and no identity is read. Preferences opens the existing T00-06
// ThemeSelector (Light / Dark / System, same runtime and storage key) in a
// Dialog; the global appearance control lives here (CLAUDE.md §19).

export type ShellAccount = {
  /** Display name. Development builds use generic demo identities only. */
  name: string;
  /** Secondary line, e.g. the role or "Demo account". */
  detail: string;
  /** Two-letter monogram (decorative). */
  initials: string;
};

export type UserMenuProps = { account: ShellAccount };

export function UserMenu({ account }: UserMenuProps) {
  const [preferencesOpen, setPreferencesOpen] = useState(false);

  const items: MenuEntry[] = [
    {
      id: "profile",
      label: "Profile",
      description: account.detail,
      icon: ProfileIcon,
    },
    { id: "preferences", label: "Preferences", icon: PreferencesIcon },
    { id: "help", label: "Help", icon: HelpIcon },
    { id: "separator", type: "separator" },
    { id: "sign-out", label: "Sign out", icon: SignOutIcon },
  ];

  const onAction = (id: string) => {
    switch (id) {
      case "preferences":
        setPreferencesOpen(true);
        break;
      case "sign-out":
        toast.info("Sign-out is not available yet", {
          description: "Accounts and sessions arrive with authentication.",
        });
        break;
      default:
        toast.info(
          `${id === "help" ? "Help" : "Profile"} is not available yet`,
          {
            description: "This area is part of a later phase.",
          },
        );
    }
  };

  return (
    <>
      <DropdownMenu
        items={items}
        onAction={onAction}
        trigger={
          <Button variant="ghost">
            <span className="inline-flex items-center gap-2">
              <span
                aria-hidden="true"
                className="inline-flex size-8 items-center justify-center rounded-full bg-surface-secondary text-caption-sm font-semibold text-text-primary"
              >
                {account.initials}
              </span>
              <span className="sr-only desktop:not-sr-only">
                {account.name}
              </span>
              <span className="sr-only">, account menu</span>
            </span>
          </Button>
        }
      />
      <Dialog
        isOpen={preferencesOpen}
        onOpenChange={setPreferencesOpen}
        size="sm"
        title="Preferences"
        description="Appearance is saved in this browser."
        actions={(close) => <Button onPress={close}>Done</Button>}
      >
        <ThemeSelector />
      </Dialog>
    </>
  );
}
