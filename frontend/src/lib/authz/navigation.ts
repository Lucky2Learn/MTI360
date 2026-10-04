import type { NavItem, Navigation } from "@/shells/navigation";

import { meets, type RequirementContext } from "./requirements";

// Permission-aware navigation (NAV-01 / NAV-02, T01-05 UI contract §8.4).
// One filter feeds the sidebar, the tablet rail, the mobile drawer and
// command search, so they can never diverge. Hidden items are removed from
// the configuration (not rendered and hidden with CSS).
//
// Rules:
// - an item is shown when its requirement is met;
// - a group (an item with children) is shown when at least one child is
//   shown, and its own link goes to its first visible child;
// - a section is shown when at least one item is shown;
// - badges stay only on visible items (they travel with the item).
// Usability only: the API authorizes every route and action (S8).

function filterItem(
  item: NavItem,
  context: RequirementContext,
): NavItem | null {
  if (!item.children?.length) {
    return meets(item.requirement, context) ? item : null;
  }
  const children = item.children.filter((child) =>
    meets(child.requirement, context),
  );
  const first = children[0];
  if (!first) return null;
  return { ...item, href: first.href, children };
}

export function filterNavigation(
  navigation: Navigation,
  context: RequirementContext,
): Navigation {
  return navigation.flatMap((section) => {
    const items = section.items.flatMap((item) => {
      const visible = filterItem(item, context);
      return visible ? [visible] : [];
    });
    return items.length > 0 ? [{ ...section, items }] : [];
  });
}
