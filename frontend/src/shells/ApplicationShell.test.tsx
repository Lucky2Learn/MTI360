import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { toast, toastQueue } from "@/design-system/components";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { ApplicationShell } from "./ApplicationShell";
import { PageContainer, PageContent } from "./PageContainer";
import { TEST_NAVIGATION } from "./test-helpers";

const navigationState = vi.hoisted(() => ({ pathname: "/app" }));
vi.mock("next/navigation", () => ({
  usePathname: () => navigationState.pathname,
  useRouter: () => ({ push: vi.fn() }),
}));

function renderShell(sidebar?: "collapsible" | "fixed") {
  return render(
    <ApplicationShell
      experienceLabel="Tenant Application"
      homeHref="/app"
      navigation={TEST_NAVIGATION}
      navigationLabel="Tenant navigation"
      sidebar={sidebar}
      account={{ name: "Demo user", detail: "Demo account", initials: "DU" }}
      search
      notifications={[]}
    >
      <PageContainer>
        <h1>Dashboard</h1>
        <PageContent>
          <p>Content</p>
        </PageContent>
      </PageContainer>
    </ApplicationShell>,
  );
}

describe("ApplicationShell", () => {
  beforeEach(() => {
    navigationState.pathname = "/app";
  });

  it("provides banner, navigation and main landmarks and passes axe", async () => {
    const { container } = renderShell();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "Tenant navigation" }),
    ).toBeInTheDocument();
    const main = screen.getByRole("main");
    expect(main).toHaveAttribute("id", "main-content");
    expect(within(main).getByRole("heading", { level: 1 })).toHaveTextContent(
      "Dashboard",
    );
    await expectNoA11yViolations(container);
  });

  it("starts with the skip link and offers the navigation drawer trigger", async () => {
    const user = userEvent.setup();
    renderShell();
    await user.tab();
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("main")).toHaveFocus();
    expect(
      screen.getByRole("button", { name: "Open navigation" }).closest("span"),
    ).toHaveClass("desktop:hidden");
  });

  it("offers search, notifications and the account menu", () => {
    renderShell();
    // Button (tablet+) and IconButton (mobile); CSS shows one of them.
    expect(screen.getAllByRole("button", { name: /^Search/ })).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: "Notifications" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Demo user, account menu" }),
    ).toHaveAttribute("aria-haspopup", "true");
  });

  it("mounts the global toast region once", async () => {
    renderShell();
    act(() => {
      toast.success("Batch schedule saved");
    });
    const regions = await screen.findAllByRole("region", {
      name: "Notifications",
    });
    expect(regions).toHaveLength(1);
    expect(within(regions[0]!).getByText("Batch schedule saved")).toBeVisible();
    act(() => toastQueue.clear());
  });

  it("links the MTI 360 identity to the experience home", () => {
    renderShell();
    expect(
      screen.getByRole("link", { name: "MTI 360, Tenant Application home" }),
    ).toHaveAttribute("href", "/app");
    expect(screen.getByText("Tenant Application")).toBeInTheDocument();
  });

  it("highlights the current route from the pathname", () => {
    navigationState.pathname = "/app/finance";
    renderShell();
    expect(screen.getByRole("link", { name: "Finance" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("collapses and expands the sidebar and offsets the content", async () => {
    const user = userEvent.setup();
    const { container } = renderShell();
    const sidebar = container.querySelector("[data-sidebar]")!;
    const main = screen.getByRole("main");
    expect(sidebar).not.toHaveAttribute("data-collapsed");
    expect(main).toHaveClass("desktop:pl-64");

    await user.click(
      screen.getByRole("button", { name: "Collapse navigation" }),
    );
    expect(sidebar).toHaveAttribute("data-collapsed");
    expect(main).not.toHaveClass("desktop:pl-64");
    expect(within(sidebar as HTMLElement).getByText("Finance")).toHaveClass(
      "sr-only",
    );

    await user.click(screen.getByRole("button", { name: "Expand navigation" }));
    expect(sidebar).not.toHaveAttribute("data-collapsed");
  });

  it("uses a desktop-only, non-collapsible sidebar in fixed mode", () => {
    const { container } = renderShell("fixed");
    expect(container.querySelector("[data-sidebar]")).toHaveClass(
      "hidden",
      "desktop:flex",
    );
    expect(
      screen.queryByRole("button", { name: "Collapse navigation" }),
    ).toBeNull();
  });
});

describe("PageContainer", () => {
  it.each([
    ["narrow", "max-w-3xl"],
    ["standard", "max-w-6xl"],
    ["wide", "max-w-7xl"],
    ["full", "max-w-none"],
  ] as const)("applies the %s width", (width, className) => {
    const { container } = render(
      <PageContainer width={width}>
        <p>Body</p>
      </PageContainer>,
    );
    expect(container.firstElementChild).toHaveClass(className, "px-4");
    expect(container.firstElementChild).toHaveAttribute(
      "data-page-width",
      width,
    );
  });

  it("uses the shared page gutter and section spacing (T00-09)", () => {
    const { container } = render(
      <PageContainer>
        <PageContent>
          <p>Body</p>
        </PageContent>
      </PageContainer>,
    );
    const page = container.firstElementChild!;
    expect(page).toHaveClass(
      "max-w-6xl",
      "px-4",
      "tablet:px-6",
      "desktop:px-8",
      "min-w-0",
    );
    expect(page.firstElementChild).toHaveClass("gap-6", "tablet:gap-8");
  });
});
