"use client";

import {
  Tab as AriaTab,
  TabList as AriaTabList,
  TabPanel as AriaTabPanel,
  Tabs as AriaTabs,
  type Key,
  type TabsProps as AriaTabsProps,
} from "react-aria-components";

import { cx, focusRing } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// Tabs (DESIGN-SYSTEM.md §46): closely related views only. React Aria provides
// the tablist/tab/tabpanel roles, arrow/Home/End keys and panel association.
// Mobile: the tab list scrolls horizontally (the native scrollbar is the
// overflow cue). Selection is shown by an indicator bar and weight, not colour
// alone.

export type TabsProps = Omit<
  AriaTabsProps,
  "className" | "style" | "children"
> & {
  children: ReactNode;
};

export function Tabs({ children, ...props }: TabsProps) {
  return (
    <AriaTabs {...props} className="flex w-full flex-col">
      {children}
    </AriaTabs>
  );
}

export type TabListProps = {
  /** Accessible name of the tab list (required). */
  "aria-label": string;
  children: ReactNode;
};

export function TabList({ children, ...props }: TabListProps) {
  return (
    <AriaTabList
      {...props}
      className="flex max-w-full gap-1 overflow-x-auto border-b border-border-subtle"
    >
      {children}
    </AriaTabList>
  );
}

export type TabProps = {
  id: Key;
  children: ReactNode;
  isDisabled?: boolean;
};

export function Tab({ id, children, isDisabled }: TabProps) {
  return (
    <AriaTab
      id={id}
      isDisabled={isDisabled}
      className={cx(
        "-mb-px flex h-control-md shrink-0 cursor-pointer items-center border-b-2 border-transparent px-3 text-body-sm font-medium whitespace-nowrap text-text-secondary",
        "transition-colors motion-reduce:transition-none",
        "data-hovered:text-text-primary",
        "data-selected:border-accent-maritime data-selected:font-semibold data-selected:text-text-primary",
        "data-disabled:cursor-not-allowed data-disabled:opacity-50",
        focusRing,
      )}
    >
      {children}
    </AriaTab>
  );
}

export type TabPanelProps = {
  id: Key;
  children: ReactNode;
};

export function TabPanel({ id, children }: TabPanelProps) {
  return (
    <AriaTabPanel id={id} className={cx("pt-4 text-body-sm", focusRing)}>
      {children}
    </AriaTabPanel>
  );
}
