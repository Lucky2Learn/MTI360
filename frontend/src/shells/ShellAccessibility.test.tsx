import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  expectHeadingOutline,
  expectNamedControls,
} from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";

import { Breadcrumbs } from "./Breadcrumbs";
import { ExperienceFrame } from "./ExperienceFrame";
import { ExperiencePlaceholder } from "./ExperiencePlaceholder";
import {
  EXPERIENCE,
  EXPERIENCES,
  resolveExperiencePage,
  type ExperienceId,
} from "./experiences";
import { flattenNavigation } from "./navigation";

// Shell accessibility contract (T00-10; docs/architecture/accessibility.md):
// landmarks, heading outline, skip link, names and keyboard entry for every
// experience, on the home page and on a nested page.

const navigationState = vi.hoisted(() => ({ pathname: "/app" }));
vi.mock("next/navigation", () => ({
  usePathname: () => navigationState.pathname,
  useRouter: () => ({ push: vi.fn() }),
}));

const IDS: ExperienceId[] = [
  EXPERIENCE.PLATFORM,
  EXPERIENCE.TENANT,
  EXPERIENCE.STUDENT,
  EXPERIENCE.PUBLIC_SITE,
];

function nestedSlug(id: ExperienceId): string[] {
  const { basePath, navigation } = EXPERIENCES[id];
  const deepest = flattenNavigation(navigation)
    .map((item) => item.href)
    .sort((a, b) => b.split("/").length - a.split("/").length)[0]!;
  return deepest.slice(basePath.length + 1).split("/");
}

function renderExperience(id: ExperienceId, slug?: string[]) {
  const page = resolveExperiencePage(id, slug)!;
  navigationState.pathname = [EXPERIENCES[id].basePath, ...(slug ?? [])].join(
    "/",
  );
  return render(
    <ThemeProvider>
      <ExperienceFrame experience={id}>
        <ExperiencePlaceholder page={page} />
      </ExperienceFrame>
    </ThemeProvider>,
  );
}

const CASES = IDS.flatMap((id) => [
  { id, label: `${id} home`, slug: undefined as string[] | undefined },
  { id, label: `${id} nested page`, slug: nestedSlug(id) },
]);

describe("shell landmarks and headings (T00-10)", () => {
  beforeEach(() => {
    navigationState.pathname = "/app";
  });

  it.each(CASES)(
    "$label: one banner and main, uniquely named navigation, one h1 in main",
    async ({ id, slug }) => {
      const { container } = renderExperience(id, slug);
      expect(screen.getAllByRole("banner")).toHaveLength(1);
      const main = screen.getByRole("main");
      expect(main).toHaveAttribute("id", "main-content");
      expect(main).toHaveAttribute("tabindex", "-1");

      const navNames = screen
        .getAllByRole("navigation")
        .map((nav) => nav.getAttribute("aria-label"));
      expect(navNames.every(Boolean)).toBe(true);
      expect(new Set(navNames).size).toBe(navNames.length);

      const outline = expectHeadingOutline(main);
      expect(outline[0]).toBe(1);
      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);

      if (id === EXPERIENCE.PUBLIC_SITE) {
        expect(screen.getAllByRole("contentinfo")).toHaveLength(1);
      } else {
        expect(screen.queryByRole("contentinfo")).toBeNull();
      }
      expectNamedControls(container);
      await expectNoA11yViolations(container);
    },
  );

  it.each(IDS)(
    "%s: the skip link is the first tab stop and moves focus to main",
    async (id) => {
      const user = userEvent.setup();
      renderExperience(id);
      await user.tab();
      const skip = screen.getByRole("link", { name: "Skip to content" });
      expect(skip).toHaveFocus();
      await user.keyboard("{Enter}");
      expect(screen.getByRole("main")).toHaveFocus();
      await user.tab();
      expect(screen.getByRole("main").contains(document.activeElement)).toBe(
        true,
      );
    },
  );
});

describe("Breadcrumbs touch targets (T00-10)", () => {
  it("gives links a 44px target on mobile and a compact one from tablet", () => {
    render(
      <Breadcrumbs
        items={[
          { label: "Tenant Application", href: "/app" },
          { label: "Finance", href: "/app/finance" },
          { label: "Fee Structure" },
        ]}
      />,
    );
    for (const link of within(
      screen.getByRole("navigation", { name: "Breadcrumb" }),
    ).getAllByRole("link")) {
      expect(link).toHaveClass("min-h-11", "tablet:min-h-6");
    }
  });
});
