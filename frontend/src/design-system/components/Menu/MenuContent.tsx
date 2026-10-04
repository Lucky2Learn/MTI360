"use client";

import {
  Menu as AriaMenu,
  MenuItem,
  Separator,
  Text,
  type Key,
} from "react-aria-components";

import type { IconComponent } from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

// Internal: menu list shared by DropdownMenu and ContextMenu (T00-07C).
// React Aria Menu: role=menu, ArrowUp/ArrowDown (wrapping), Home/End,
// type-ahead, Enter/Space activate, Escape closes, disabled items skipped.
// Destructive items: an error-coloured icon at rest and error-text on an
// error-surface when focused/hovered — never colour alone (the label says what
// happens). The label stays text-primary at rest (chosen in T00-07C when Dark
// error-text on surface-elevated was 3.79:1; INC-24, resolved in T00-10A).

export type MenuAction = {
  id: string;
  label: string;
  description?: string;
  icon?: IconComponent;
  isDisabled?: boolean;
  tone?: "default" | "destructive";
};

export type MenuSeparator = { id: string; type: "separator" };

export type MenuEntry = MenuAction | MenuSeparator;

const isSeparator = (entry: MenuEntry): entry is MenuSeparator =>
  "type" in entry && entry.type === "separator";

export function MenuContent({
  label,
  items,
  onAction,
  initialFocus,
  describedBy,
}: {
  /** Needed when there is no trigger (ContextMenu); a MenuTrigger labels the menu itself. */
  label?: string;
  items: MenuEntry[];
  onAction: (id: string) => void;
  /** Item that receives focus when the menu opens without a trigger (ContextMenu). */
  initialFocus?: "first" | "last";
  /** Id of static context that describes the menu (DropdownMenu header). */
  describedBy?: string;
}) {
  return (
    <AriaMenu
      aria-label={label}
      aria-describedby={describedBy}
      // React Aria focus strategy for an opened menu (WAI-ARIA menu pattern),
      // not DOM autofocus on page load.
      // eslint-disable-next-line jsx-a11y/no-autofocus
      autoFocus={initialFocus}
      onAction={(key: Key) => onAction(String(key))}
      // a11y-focus: menu container; menu items show the focus ring
      className="flex min-w-48 flex-col gap-1 p-1 outline-none"
    >
      {items.map((entry) =>
        isSeparator(entry) ? (
          <Separator
            key={entry.id}
            className="my-1 border-t border-border-subtle"
          />
        ) : (
          <MenuItem
            key={entry.id}
            id={entry.id}
            textValue={entry.label}
            isDisabled={entry.isDisabled}
            className={cx(
              "flex min-h-control-lg cursor-pointer items-center gap-3 rounded-sm px-3 py-2 text-body-sm outline-none tablet:min-h-control-md",
              entry.tone === "destructive"
                ? "text-text-primary data-focused:bg-error-surface data-focused:text-error-text"
                : "text-text-primary data-focused:bg-surface-hover",
              "data-focus-visible:outline-solid data-focus-visible:outline-(length:--focus-ring-width) data-focus-visible:-outline-offset-2 data-focus-visible:outline-focus-ring",
              "data-disabled:cursor-not-allowed data-disabled:opacity-50",
            )}
          >
            {entry.icon && (
              <entry.icon
                aria-hidden="true"
                className={cx(
                  "size-4 shrink-0",
                  entry.tone === "destructive" && "text-error",
                )}
              />
            )}
            <span className="flex min-w-0 flex-col">
              <Text slot="label">{entry.label}</Text>
              {entry.description && (
                <Text
                  slot="description"
                  className="text-caption text-text-secondary"
                >
                  {entry.description}
                </Text>
              )}
            </span>
          </MenuItem>
        ),
      )}
    </AriaMenu>
  );
}
