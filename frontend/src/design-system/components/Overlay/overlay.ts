import { cx } from "@/design-system/lib/cx";

// Shared overlay styling (T00-07C). One definition for every floating surface
// so Select, Combobox, DatePicker (07B), Popover, Menu, Tooltip, Dialog and
// Drawer stay visually consistent. Surfaces use semantic tokens only and
// follow the theme because React Aria portals them into <body>, under the
// themed <html>. Entry fades use @starting-style and are removed under
// prefers-reduced-motion; no information depends on motion.

/** Anchored floating surface (popovers, listboxes, menus, calendar). */
export const popoverSurface = cx(
  "z-(--z-dropdown) rounded-md border border-border-default bg-surface-elevated text-text-primary shadow-lg outline-none",
  "transition-opacity starting:opacity-0 motion-reduce:transition-none",
);

/** Full-screen scrim behind modal dialogs and drawers. */
export const modalBackdrop = cx(
  "fixed inset-0 flex bg-overlay-scrim",
  "transition-opacity starting:opacity-0 motion-reduce:transition-none",
);

/** Raised panel for dialogs and drawers. */
export const panelSurface =
  "flex flex-col overflow-hidden border border-border-default bg-surface-elevated text-text-primary shadow-lg outline-none";
