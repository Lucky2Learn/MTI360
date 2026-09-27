"use client";

import { MenuTrigger, Popover, type PopoverProps } from "react-aria-components";

import { popoverSurface } from "@/design-system/components/Overlay/overlay";
import { cx } from "@/design-system/lib/cx";

import { MenuContent, type MenuEntry } from "./MenuContent";

import type { ReactElement } from "react";

// DropdownMenu (T00-07C): a list of actions opened from a button — row
// actions, export, bulk actions, account actions. React Aria MenuTrigger: the
// trigger gets aria-haspopup/aria-expanded; Enter/Space/ArrowDown open with
// focus on the first item (ArrowUp: last); Escape closes and returns focus to
// the trigger; the menu flips/shifts to stay in the viewport. Items are
// business-neutral: callers pass labels and handle `onAction(id)`.
// The menu is labelled by its trigger (ARIA menu-button pattern), so the
// trigger must have an accessible name. Submenus are intentionally not
// provided (not needed by current specs).

export type DropdownMenuProps = {
  /** Pressable trigger (Button / IconButton with an accessible name). */
  trigger: ReactElement;
  items: MenuEntry[];
  onAction: (id: string) => void;
  placement?: PopoverProps["placement"];
  isOpen?: boolean;
  onOpenChange?: (isOpen: boolean) => void;
};

export function DropdownMenu({
  trigger,
  items,
  onAction,
  placement = "bottom end",
  isOpen,
  onOpenChange,
}: DropdownMenuProps) {
  return (
    <MenuTrigger isOpen={isOpen} onOpenChange={onOpenChange}>
      {trigger}
      <Popover
        placement={placement}
        offset={4}
        containerPadding={16}
        className={cx(popoverSurface, "max-h-80 max-w-full overflow-auto")}
      >
        <MenuContent items={items} onAction={onAction} />
      </Popover>
    </MenuTrigger>
  );
}
