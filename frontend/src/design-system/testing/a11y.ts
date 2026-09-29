import { within } from "@testing-library/react";
import { expect } from "vitest";

import type { UserEvent } from "@testing-library/user-event";

// Shared accessibility assertions for component tests (T00-10). They add what
// Testing Library and jest-dom do not provide directly: focus order, focus
// containment, "every control is named" and "focus is visibly styled".
// Contract: docs/architecture/accessibility.md §12.

/** Roles of interactive controls that must always have an accessible name. */
export const INTERACTIVE_ROLES = [
  "button",
  "link",
  "checkbox",
  "radio",
  "switch",
  "textbox",
  "searchbox",
  "combobox",
  "listbox",
  "option",
  "menuitem",
  "menuitemcheckbox",
  "menuitemradio",
  "tab",
  "spinbutton",
  "slider",
] as const;

/** Every interactive control inside `container` has a non-empty accessible name. */
export function expectNamedControls(container: HTMLElement): void {
  const unnamed: string[] = [];
  for (const role of INTERACTIVE_ROLES) {
    for (const element of within(container).queryAllByRole(role, {
      hidden: false,
    })) {
      try {
        expect(element).toHaveAccessibleName();
      } catch {
        unnamed.push(`${role}: ${element.outerHTML.slice(0, 80)}`);
      }
    }
  }
  expect(unnamed).toEqual([]);
}

/** Accessible label of the focused element (aria-label, else its text). */
function focusedLabel(): string {
  const active = document.activeElement;
  if (!active || active === document.body) return "<body>";
  return (
    active.getAttribute("aria-label") ??
    active.textContent?.trim().replace(/\s+/g, " ") ??
    active.tagName
  );
}

/**
 * Presses Tab `count` times and returns what received focus, in order —
 * use it to assert keyboard order: expect(await tabSequence(user, 3)).toEqual([…]).
 */
export async function tabSequence(
  user: UserEvent,
  count: number,
  { shift = false }: { shift?: boolean } = {},
): Promise<string[]> {
  const labels: string[] = [];
  for (let press = 0; press < count; press += 1) {
    await user.tab({ shift });
    labels.push(focusedLabel());
  }
  return labels;
}

/**
 * Tabs forwards and backwards `presses` times and asserts that focus never
 * leaves `container` (modal dialogs, drawers, alert dialogs).
 */
export async function expectFocusContained(
  user: UserEvent,
  container: HTMLElement,
  presses = 8,
): Promise<void> {
  for (let press = 0; press < presses; press += 1) {
    await user.tab({ shift: press % 2 === 1 });
    expect(
      container.contains(document.activeElement),
      `focus left the container after ${press + 1} presses (on ${focusedLabel()})`,
    ).toBe(true);
  }
}

/** Focus indicator classes of the shared mechanisms (lib/cx, Field). */
const RING =
  /(?:^|\s)(?:data-focus-visible:|focus-visible:|data-focused:|data-focus-within:)outline-focus-ring(?:\s|$)/;

/**
 * The element (or the wrapper that draws its ring, e.g. a text field group)
 * uses the token focus ring for keyboard focus. jsdom cannot render outlines,
 * so this checks the styling contract; Chromium verification checks pixels.
 */
export function expectFocusRing(element: Element): void {
  let node: Element | null = element;
  for (let depth = 0; node && depth < 4; depth += 1) {
    if (RING.test(node.getAttribute("class") ?? "")) return;
    node = node.parentElement;
  }
  throw new Error(
    `no token focus ring on ${element.outerHTML.slice(0, 120)} or its wrappers`,
  );
}

/**
 * Heading convention (docs/architecture/accessibility.md): exactly one h1 per
 * page, it comes first, and no level is skipped going down (h2 → h4 is not
 * allowed; going back up is fine). Returns the outline for extra assertions.
 */
export function expectHeadingOutline(container: HTMLElement): number[] {
  const levels = within(container)
    .queryAllByRole("heading")
    .map((heading) => Number(heading.tagName.slice(1)) || 2);
  expect(levels.filter((level) => level === 1)).toHaveLength(1);
  expect(levels[0]).toBe(1);
  const skips = levels.flatMap((level, index) =>
    index > 0 && level > levels[index - 1]! + 1
      ? [`h${levels[index - 1]} → h${level}`]
      : [],
  );
  expect(skips).toEqual([]);
  return levels;
}
