"use client";

import { useState, type ReactNode } from "react";

import {
  Button,
  Dialog,
  DropdownMenu,
  toast,
  type MenuAction,
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
// Preferences opens the existing T00-06 ThemeSelector (Light / Dark / System,
// same runtime and storage key) in a Dialog; the global appearance control
// lives here (CLAUDE.md §19). Profile and Help are not built yet and say so.
//
// T01-09A: an experience with a session passes `session` — a menu header
// (identity, institute, roles: SESSION-01), extra items (the mobile
// Institute / Campus entries) and the real sign-out. Without it (experiences
// that have no authentication yet) Sign out explains it is not available.

export type ShellAccount = {
  /** Display name. Development builds use generic demo identities only. */
  name: string;
  /** Secondary line, e.g. the role or "Demo account". */
  detail: string;
  /** Two-letter monogram (decorative). */
  initials: string;
};

export type UserMenuSession = {
  /** Static context above the items (no interactive content). */
  header: ReactNode;
  /** Items placed before Preferences, e.g. Institute and Campus. */
  items?: MenuAction[];
  onItemAction?: (id: string) => void;
  onSignOut: () => void;
};

export type UserMenuProps = {
  account: ShellAccount;
  session?: UserMenuSession;
};

export function UserMenu({ account, session }: UserMenuProps) {
  const [preferencesOpen, setPreferencesOpen] = useState(false);

  const items: MenuEntry[] = [
    ...(session?.items ?? []),
    {
      id: "profile",
      label: "Profile",
      description: session ? undefined : account.detail,
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
        if (session) {
          session.onSignOut();
          break;
        }
        toast.info("Sign-out is not available yet", {
          description: "Accounts and sessions arrive with authentication.",
        });
        break;
      case "profile":
      case "help":
        toast.info(
          `${id === "help" ? "Help" : "Profile"} is not available yet`,
          {
            description: "This area is part of a later phase.",
          },
        );
        break;
      default:
        session?.onItemAction?.(id);
    }
  };

  return (
    <>
      <DropdownMenu
        items={items}
        onAction={onAction}
        header={session?.header}
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
