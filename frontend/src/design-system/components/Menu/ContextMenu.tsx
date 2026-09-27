"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Popover } from "react-aria-components";

import { popoverSurface } from "@/design-system/components/Overlay/overlay";
import { cx } from "@/design-system/lib/cx";

import { MenuContent, type MenuEntry } from "./MenuContent";

// ContextMenu (T00-07C): actions for the region under the pointer or the
// focused element. React Aria has no context-menu trigger, so this wraps its
// Popover + Menu:
// - pointer: right-click (contextmenu event) opens at the pointer position;
// - keyboard: Shift+F10 or the ContextMenu key opens at the focused element;
// - Escape / selection / outside click close it and focus returns to the
//   element that was focused before opening.
// A context menu is a shortcut only: every action must also be reachable
// another way (e.g. a DropdownMenu row-action button) — right-click must never
// be the only path to important functionality.

export type ContextMenuProps = {
  /** Accessible name of the menu, e.g. "Document actions". */
  label: string;
  items: MenuEntry[];
  onAction: (id: string) => void;
  /** The region that responds to the context menu (should contain focusable content). */
  children: ReactNode;
};

type Point = { x: number; y: number };

export function ContextMenu({
  label,
  items,
  onAction,
  children,
}: ContextMenuProps) {
  const regionRef = useRef<HTMLDivElement>(null);
  const anchorRef = useRef<HTMLSpanElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const [point, setPoint] = useState<Point | null>(null);

  useEffect(() => {
    const region = regionRef.current;
    if (!region) return;
    const open = (at: Point) => {
      returnFocus.current =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
      setPoint(at);
    };
    const onContextMenu = (event: MouseEvent) => {
      event.preventDefault();
      open({ x: event.clientX, y: event.clientY });
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (
        (event.shiftKey && event.key === "F10") ||
        event.key === "ContextMenu"
      ) {
        event.preventDefault();
        const target =
          event.target instanceof HTMLElement ? event.target : region;
        const rect = target.getBoundingClientRect();
        open({ x: rect.left, y: rect.bottom });
      }
    };
    region.addEventListener("contextmenu", onContextMenu);
    region.addEventListener("keydown", onKeyDown);
    return () => {
      region.removeEventListener("contextmenu", onContextMenu);
      region.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  const close = () => {
    setPoint(null);
    const target = returnFocus.current;
    returnFocus.current = null;
    if (target?.isConnected) requestAnimationFrame(() => target.focus());
  };

  return (
    <div ref={regionRef}>
      {children}
      <span
        ref={anchorRef}
        aria-hidden="true"
        className="pointer-events-none fixed size-0"
        style={point ? { left: point.x, top: point.y } : undefined}
      />
      <Popover
        aria-label={label}
        triggerRef={anchorRef}
        isOpen={point !== null}
        onOpenChange={(isOpen) => {
          if (!isOpen) close();
        }}
        placement="bottom start"
        offset={2}
        containerPadding={16}
        className={cx(popoverSurface, "max-h-80 max-w-full overflow-auto")}
      >
        <MenuContent
          label={label}
          items={items}
          initialFocus="first"
          onAction={(id) => {
            onAction(id);
            close();
          }}
        />
      </Popover>
    </div>
  );
}
