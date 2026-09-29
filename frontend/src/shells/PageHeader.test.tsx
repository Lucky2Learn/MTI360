import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Badge, Button } from "@/design-system/components";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Breadcrumbs } from "./Breadcrumbs";
import { PageHeader } from "./PageHeader";
import { SkipNavigation } from "./SkipNavigation";

const TRAIL = [
  { label: "Tenant Application", href: "/app" },
  { label: "Admissions", href: "/app/admissions" },
  { label: "Leads", href: "/app/admissions/leads" },
  { label: "Lead detail" },
];

describe("Breadcrumbs", () => {
  it("renders a labelled navigation with an ordered list and passes axe", async () => {
    const { container } = render(<Breadcrumbs items={TRAIL} />);
    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    const list = within(nav).getByRole("list");
    expect(list.tagName).toBe("OL");
    expect(within(nav).getByRole("link", { name: "Leads" })).toHaveAttribute(
      "href",
      "/app/admissions/leads",
    );
    await expectNoA11yViolations(container);
  });

  it("marks the last item as the current page, without a link", () => {
    render(<Breadcrumbs items={TRAIL} />);
    const current = screen.getByText("Lead detail");
    expect(current).toHaveAttribute("aria-current", "page");
    expect(current.closest("a")).toBeNull();
  });

  it("collapses the middle items on mobile only", () => {
    render(<Breadcrumbs items={TRAIL} />);
    const admissions = screen.getByRole("link", { name: "Admissions" });
    expect(admissions.closest("li")).toHaveClass("hidden", "tablet:flex");
    expect(
      screen.getByRole("link", { name: "Leads" }).closest("li"),
    ).not.toHaveClass("hidden");
    expect(screen.getByText("…").closest("li")).toHaveClass("tablet:hidden");
  });

  it("does not collapse short trails and renders nothing when empty", () => {
    const { container, rerender } = render(
      <Breadcrumbs items={TRAIL.slice(2)} />,
    );
    expect(screen.queryByText("…")).toBeNull();
    rerender(<Breadcrumbs items={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("PageHeader", () => {
  it("renders breadcrumbs, the page h1, status, description and actions", async () => {
    const { container } = render(
      <PageHeader
        breadcrumbs={TRAIL.slice(0, 2).concat({ label: "Students" })}
        title="Students"
        description="Cadets enrolled across all batches."
        status={<Badge tone="success">Active</Badge>}
        actions={<Button>Add student</Button>}
      >
        <p>Secondary content</p>
      </PageHeader>,
    );
    expect(
      screen.getByRole("heading", { level: 1, name: "Students" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "Breadcrumb" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(
      screen.getByText("Cadets enrolled across all batches."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add student" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Secondary content")).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("stacks actions on mobile and lets them wrap below a long title from tablet (T00-09)", () => {
    render(
      <PageHeader
        title="Pre-Sea Training Operations Overview — Anglo-Eastern Maritime Training Centre, Navi Mumbai"
        actions={
          <>
            <Button variant="secondary">Export report</Button>
            <Button variant="secondary">Share</Button>
            <Button>Schedule batch</Button>
          </>
        }
      />,
    );
    const actions = screen.getByRole("button", {
      name: "Schedule batch",
    }).parentElement!;
    // Mobile: full-width column, primary (last in the DOM) on top.
    expect(actions).toHaveClass("flex-col-reverse", "tablet:flex-row");
    expect(actions).toHaveClass("tablet:flex-wrap");
    expect(actions).not.toHaveClass("tablet:shrink-0");
    // Tablet+: the title keeps at least 24rem; the actions wrap otherwise.
    const titleBlock = screen.getByRole("heading", { level: 1 }).parentElement!
      .parentElement!;
    expect(titleBlock).toHaveClass(
      "min-w-0",
      "tablet:flex-1",
      "tablet:basis-96",
    );
    expect(titleBlock.parentElement).toHaveClass(
      "tablet:flex-row",
      "tablet:flex-wrap",
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveClass(
      "break-words",
    );
    // DOM (focus) order is unchanged.
    expect(screen.getAllByRole("button").map((b) => b.textContent)).toEqual([
      "Export report",
      "Share",
      "Schedule batch",
    ]);
  });

  it("renders only the title when nothing else is supplied", () => {
    render(<PageHeader title="Settings" />);
    expect(screen.queryByRole("navigation")).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Settings",
    );
  });
});

describe("SkipNavigation", () => {
  it("is the first tab stop and moves focus to the main content", async () => {
    const user = userEvent.setup();
    render(
      <>
        <SkipNavigation />
        <button type="button">Menu</button>
        <main id="main-content" tabIndex={-1}>
          <button type="button">First action</button>
        </main>
      </>,
    );
    await user.tab();
    const skip = screen.getByRole("link", { name: "Skip to content" });
    expect(skip).toHaveFocus();
    expect(skip).toHaveClass("sr-only", "focus:not-sr-only");
    await user.keyboard("{Enter}");
    expect(screen.getByRole("main")).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "First action" })).toHaveFocus();
  });

  it("falls back to the in-page link when the target is missing", async () => {
    const user = userEvent.setup();
    render(<SkipNavigation targetId="missing" label="Skip" />);
    const skip = screen.getByRole("link", { name: "Skip" });
    expect(skip).toHaveAttribute("href", "#missing");
    await user.click(skip);
    expect(skip).toBeInTheDocument();
  });
});
