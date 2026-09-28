import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastRegion, toastQueue } from "@/design-system/components";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { THEME_STORAGE_KEY } from "@/design-system/theme/theme";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";

import { CommandSearch } from "./CommandSearch";
import {
  NotificationCenter,
  type ShellNotification,
} from "./NotificationCenter";
import { ShellError, ShellLoading } from "./ShellBoundaries";
import { TEST_NAVIGATION } from "./test-helpers";
import { UserMenu } from "./UserMenu";

const router = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const ACCOUNT = { name: "Demo user", detail: "Demo account", initials: "DU" };

const NOTIFICATIONS: ShellNotification[] = [
  {
    id: "n1",
    title: "Batch DNS 2026-B timetable published",
    description: "Classes start on Monday.",
    timestamp: "2026-09-28T09:15:00+05:30",
    timeLabel: "25 min ago",
    read: false,
  },
  {
    id: "n2",
    title: "Medical certificate verified",
    timestamp: "2026-09-27T16:40:00+05:30",
    timeLabel: "Yesterday",
    read: false,
  },
  {
    id: "n3",
    title: "Weekly attendance summary ready",
    timestamp: "2026-09-26T08:00:00+05:30",
    timeLabel: "2 days ago",
    read: true,
  },
];

afterEach(() => {
  act(() => toastQueue.clear());
  router.push.mockReset();
  window.localStorage.clear();
});

describe("UserMenu", () => {
  function renderMenu() {
    return render(
      <ThemeProvider>
        <UserMenu account={ACCOUNT} />
        <ToastRegion />
      </ThemeProvider>,
    );
  }

  it("opens an account menu with the structural items and passes axe", async () => {
    const user = userEvent.setup();
    renderMenu();
    const trigger = screen.getByRole("button", {
      name: "Demo user, account menu",
    });
    await user.click(trigger);
    const menu = screen.getByRole("menu");
    expect(
      within(menu)
        .getAllByRole("menuitem")
        .map((item) => item.textContent),
    ).toEqual(["ProfileDemo account", "Preferences", "Help", "Sign out"]);
    await expectNoA11yViolations(document.body);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("opens Preferences with the existing theme selector", async () => {
    const user = userEvent.setup();
    renderMenu();
    await user.click(
      screen.getByRole("button", { name: "Demo user, account menu" }),
    );
    await user.click(screen.getByRole("menuitem", { name: "Preferences" }));
    const dialog = await screen.findByRole("dialog", { name: "Preferences" });
    await user.click(within(dialog).getByRole("radio", { name: /Dark/ }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    await expectNoA11yViolations(document.body);
    await user.click(within(dialog).getByRole("button", { name: "Done" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("explains that sign-out is not available yet (no authentication)", async () => {
    const user = userEvent.setup();
    renderMenu();
    await user.click(
      screen.getByRole("button", { name: "Demo user, account menu" }),
    );
    await user.click(screen.getByRole("menuitem", { name: "Sign out" }));
    expect(
      await screen.findByText("Sign-out is not available yet"),
    ).toBeInTheDocument();
  });
});

describe("NotificationCenter", () => {
  it("includes the unread count in the trigger name and lists notifications", async () => {
    const user = userEvent.setup();
    render(<NotificationCenter notifications={NOTIFICATIONS} />);
    const trigger = screen.getByRole("button", {
      name: "Notifications, 2 unread",
    });
    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Notifications" });
    const items = within(dialog).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(
      within(items[0]!).getByRole("button", {
        name: /^Unread:s*Batch DNS 2026-B timetable published/,
      }),
    ).toBeInTheDocument();
    expect(
      within(items[2]!).getByRole("button", {
        name: /^Weekly attendance summary ready/,
      }),
    ).toBeInTheDocument();
    await expectNoA11yViolations(document.body);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("marks one or all notifications as read", async () => {
    const user = userEvent.setup();
    render(<NotificationCenter notifications={NOTIFICATIONS} />);
    await user.click(
      screen.getByRole("button", { name: "Notifications, 2 unread" }),
    );
    await user.click(
      screen.getByRole("button", { name: /^Unread:s*Medical certificate/ }),
    );
    // The trigger is aria-hidden while the popover is open (hidden: true).
    expect(
      screen.getByRole("button", {
        name: "Notifications, 1 unread",
        hidden: true,
      }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Mark all as read" }));
    expect(
      screen.getByRole("button", { name: "Notifications", hidden: true }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Mark all as read" }),
    ).toBeDisabled();
  });

  it("shows an empty state when there are no notifications", async () => {
    const user = userEvent.setup();
    render(<NotificationCenter notifications={[]} />);
    await user.click(screen.getByRole("button", { name: "Notifications" }));
    expect(
      screen.getByRole("heading", { name: "No notifications" }),
    ).toBeInTheDocument();
    await expectNoA11yViolations(document.body);
  });
});

describe("CommandSearch", () => {
  function renderSearch() {
    return render(
      <CommandSearch
        experienceLabel="Tenant Application"
        navigation={TEST_NAVIGATION}
      />,
    );
  }

  it("opens from the trigger with focus in the search field and passes axe", async () => {
    const user = userEvent.setup();
    renderSearch();
    await user.click(screen.getAllByRole("button", { name: "Search" })[0]!);
    const dialog = screen.getByRole("dialog", { name: "Search" });
    await waitFor(() =>
      expect(
        within(dialog).getByRole("searchbox", { name: "Search pages" }),
      ).toHaveFocus(),
    );
    expect(within(dialog).getByRole("status")).toHaveTextContent("7 pages");
    await expectNoA11yViolations(document.body);
  });

  it("opens with Ctrl+K and restores focus when closed with Escape", async () => {
    const user = userEvent.setup();
    renderSearch();
    const trigger = screen.getAllByRole("button", { name: "Search" })[1]!;
    trigger.focus();
    await user.keyboard("{Control>}k{/Control}");
    const dialog = await screen.findByRole("dialog", { name: "Search" });
    expect(dialog).toBeInTheDocument();
    await user.keyboard("{Escape}");
    // The first Escape clears the (empty) field or closes the dialog.
    if (screen.queryByRole("dialog")) await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("filters pages, announces the count and opens the first match on Enter", async () => {
    const user = userEvent.setup();
    renderSearch();
    await user.click(screen.getAllByRole("button", { name: "Search" })[0]!);
    const field = await screen.findByRole("searchbox", {
      name: "Search pages",
    });
    await user.type(field, "lead");
    expect(screen.getByRole("status")).toHaveTextContent("1 page");
    expect(
      within(screen.getByRole("list", { name: "Pages" })).getByRole("link", {
        name: "Leads",
      }),
    ).toHaveAttribute("href", "/app/admissions/leads");
    await user.keyboard("{Enter}");
    expect(router.push).toHaveBeenCalledWith("/app/admissions/leads");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("explains when nothing matches", async () => {
    const user = userEvent.setup();
    renderSearch();
    await user.click(screen.getAllByRole("button", { name: "Search" })[0]!);
    await user.type(
      await screen.findByRole("searchbox", { name: "Search pages" }),
      "zzz",
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "No pages match “zzz”.",
    );
    expect(screen.queryByRole("list", { name: "Pages" })).toBeNull();
  });
});

describe("Shell boundaries", () => {
  it("announces loading with skeletons and passes axe", async () => {
    const { container } = render(<ShellLoading label="Loading tenants" />);
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveTextContent("Loading tenants");
    expect(
      container.querySelectorAll("[data-skeleton]").length,
    ).toBeGreaterThan(0);
    await expectNoA11yViolations(container);
  });

  it("shows a safe error with retry, home link and reference only", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    const { container } = render(
      <ShellError onRetry={onRetry} homeHref="/platform" reference="1234567" />,
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Page error",
    );
    expect(
      screen.getByRole("heading", { name: "This page could not be loaded" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to home" })).toHaveAttribute(
      "href",
      "/platform",
    );
    expect(screen.getByText("1234567")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
    await expectNoA11yViolations(container);
  });
});
