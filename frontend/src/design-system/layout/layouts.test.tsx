import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button, Card, CardHeader } from "@/design-system/components";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { ActionBar } from "./ActionBar";
import { Show } from "./Show";
import { SplitLayout } from "./SplitLayout";

describe("SplitLayout", () => {
  const split = (props = {}) =>
    render(
      <SplitLayout
        primary={<p>Primary content</p>}
        secondary={<p>Secondary content</p>}
        {...props}
      />,
    );
  const slot = (name: string) =>
    document.querySelector(`[data-slot="${name}"]`)!;

  it("stacks below desktop and splits 2:1 from desktop by default", () => {
    const { container } = split();
    const layout = container.firstElementChild!;
    expect(layout).toHaveAttribute("data-ratio", "2:1");
    expect(layout).toHaveClass(
      "grid",
      "grid-cols-1",
      "desktop:grid-cols-3",
      "gap-6",
    );
    expect(slot("primary")).toHaveClass("desktop:col-span-2", "min-w-0");
    expect(slot("secondary")).toHaveClass("desktop:col-span-1", "min-w-0");
  });

  it.each([
    ["1:1", "tablet", "tablet:grid-cols-2", "tablet:col-span-1"],
    ["3:1", "large", "large:grid-cols-4", "large:col-span-3"],
  ] as const)(
    "supports ratio %s side by side from %s",
    (ratio, stackBelow, columns, primarySpan) => {
      const { container } = split({ ratio, stackBelow });
      expect(container.firstElementChild).toHaveClass(columns);
      expect(container.firstElementChild).not.toHaveClass(
        "desktop:grid-cols-3",
      );
      expect(slot("primary")).toHaveClass(primarySpan);
    },
  );

  it("keeps the DOM order equal to the visual order", () => {
    const { container, rerender } = split();
    const order = () =>
      [...container.firstElementChild!.children].map((child) =>
        child.getAttribute("data-slot"),
      );
    expect(order()).toEqual(["primary", "secondary"]);
    rerender(
      <SplitLayout
        primary={<p>Primary content</p>}
        secondary={<p>Secondary content</p>}
        secondaryPosition="start"
      />,
    );
    expect(order()).toEqual(["secondary", "primary"]);
    expect(container.firstElementChild!.className).not.toMatch(/order-/);
  });

  it("composes cards and passes axe", async () => {
    const { container } = render(
      <SplitLayout
        primary={
          <Card as="section" aria-labelledby="profile">
            <CardHeader title="Cadet profile" titleAs="h2" titleId="profile" />
          </Card>
        }
        secondary={
          <Card as="section" aria-labelledby="actions">
            <CardHeader title="Next steps" titleAs="h2" titleId="actions" />
            <Button>Verify documents</Button>
          </Card>
        }
      />,
    );
    expect(screen.getAllByRole("region")).toHaveLength(2);
    await expectNoA11yViolations(container);
  });
});

describe("Show", () => {
  it("renders a layout-neutral wrapper when no breakpoint is set", () => {
    render(<Show>Always</Show>);
    expect(screen.getByText("Always")).toHaveClass("contents");
  });

  it("hides content until a breakpoint with from", () => {
    render(<Show from="desktop">Full panel</Show>);
    const wrapper = screen.getByText("Full panel");
    expect(wrapper).toHaveClass("hidden", "desktop:contents");
    expect(wrapper).toHaveAttribute("data-show-from", "desktop");
  });

  it("hides content from a breakpoint with below", () => {
    render(<Show below="tablet">Compact summary</Show>);
    expect(screen.getByText("Compact summary")).toHaveClass(
      "contents",
      "tablet:hidden",
    );
  });

  it("combines from and below for a single tier", () => {
    render(
      <Show from="tablet" below="desktop" as="span">
        Tablet only
      </Show>,
    );
    const wrapper = screen.getByText("Tablet only");
    expect(wrapper.tagName).toBe("SPAN");
    expect(wrapper).toHaveClass("hidden", "tablet:contents", "desktop:hidden");
  });

  it("server-renders identical markup (no viewport detection)", async () => {
    const { renderToString } = await import("react-dom/server");
    const markup = renderToString(<Show from="large">Large</Show>);
    expect(markup).toContain('class="hidden large:contents"');
  });
});

describe("ActionBar", () => {
  it("stacks full width with the primary action on top on mobile, a wrapping row from tablet", () => {
    render(
      <ActionBar>
        <Button variant="tertiary">Cancel</Button>
        <Button>Submit</Button>
      </ActionBar>,
    );
    const bar = screen.getByRole("button", { name: "Submit" }).parentElement!;
    expect(bar).toHaveClass(
      "flex-col-reverse",
      "tablet:flex-row",
      "tablet:flex-wrap",
      "tablet:justify-end",
    );
    expect(bar).not.toHaveAttribute("role");
  });

  it("supports alignment, a divider and a labelled group", async () => {
    const { container } = render(
      <ActionBar align="between" divider aria-label="Form actions">
        <Button variant="secondary">Save draft</Button>
        <Button>Submit enquiry</Button>
      </ActionBar>,
    );
    const group = screen.getByRole("group", { name: "Form actions" });
    expect(group).toHaveClass(
      "tablet:justify-between",
      "border-t",
      "border-border-subtle",
    );
    expect(
      screen.getAllByRole("button").map((button) => button.textContent),
    ).toEqual(["Save draft", "Submit enquiry"]);
    await expectNoA11yViolations(container);
  });
});
