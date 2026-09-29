import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Badge, Button } from "@/design-system/components";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Container } from "./Container";
import { Grid, GridItem } from "./Grid";
import { Inline } from "./Inline";
import { Section } from "./Section";
import { Stack } from "./Stack";

// jsdom does not compute Tailwind layout; these tests pin the responsive
// contract (which utilities apply at which breakpoint), semantics and axe.
// Real layout at 390/768/1024/1440 is verified in Chromium.

const LONG_NAME =
  "Anglo-Eastern Maritime Training Centre for Advanced Seafarer Competency Development";
const LONG_EMAIL =
  "admissions.coordinator.pre-sea-training@angloeasternmaritimetrainingcentre.example";

describe("Container", () => {
  it("centres content at the standard width with the page gutter by default", () => {
    render(<Container>Content</Container>);
    const container = screen.getByText("Content");
    expect(container).toHaveAttribute("data-width", "standard");
    expect(container).toHaveClass(
      "mx-auto",
      "w-full",
      "min-w-0",
      "max-w-6xl",
      "px-4",
      "tablet:px-6",
      "desktop:px-8",
    );
  });

  it.each([
    ["narrow", "max-w-3xl"],
    ["wide", "max-w-7xl"],
    ["full", "max-w-none"],
  ] as const)("supports the %s content width", (width, utility) => {
    render(<Container width={width}>Content</Container>);
    expect(screen.getByText("Content")).toHaveClass(utility);
  });

  it("can omit the gutter and render as a labelled section", async () => {
    const { container } = render(
      <Container as="section" gutter={false} aria-label="Batch overview">
        <p>Content</p>
      </Container>,
    );
    const region = screen.getByRole("region", { name: "Batch overview" });
    expect(region.className).not.toContain("px-4");
    await expectNoA11yViolations(container);
  });
});

describe("Stack", () => {
  it("stacks children vertically with the standard 16px gap by default", () => {
    render(
      <Stack>
        <p>First</p>
        <p>Second</p>
      </Stack>,
    );
    const stack = screen.getByText("First").parentElement!;
    expect(stack).toHaveClass("flex", "flex-col", "gap-4", "items-stretch");
    expect(stack).toHaveClass("min-w-0");
  });

  it("uses responsive spacing for section-level gaps and supports alignment", () => {
    render(
      <Stack gap="2xl" align="center">
        <p>Only</p>
      </Stack>,
    );
    const stack = screen.getByText("Only").parentElement!;
    expect(stack).toHaveClass("gap-8", "tablet:gap-12", "items-center");
  });

  it("can be a list with list semantics", async () => {
    const { container } = render(
      <Stack as="ul" gap="xs" aria-label="Required documents">
        <li>INDoS number</li>
        <li>Medical fitness certificate</li>
      </Stack>,
    );
    const list = screen.getByRole("list", { name: "Required documents" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    await expectNoA11yViolations(container);
  });
});

describe("Inline", () => {
  it("lays children out in a wrapping row, each capped to the row width", () => {
    render(
      <Inline>
        <Badge tone="success">Verified</Badge>
        <Badge tone="warning">Fee overdue</Badge>
      </Inline>,
    );
    const row = screen.getByText("Verified").closest("div.flex")!;
    expect(row).toHaveClass(
      "flex-row",
      "flex-wrap",
      "items-center",
      "gap-3",
      "*:min-w-0",
      "*:max-w-full",
    );
  });

  it("can disable wrapping and set alignment and justification", () => {
    render(
      <Inline wrap={false} align="baseline" justify="between" gap="xs">
        <span>Left</span>
        <span>Right</span>
      </Inline>,
    );
    const row = screen.getByText("Left").parentElement!;
    expect(row).toHaveClass(
      "flex-nowrap",
      "items-baseline",
      "justify-between",
      "gap-2",
    );
  });

  it.each([
    ["tablet", "tablet:flex-row", "tablet:items-center"],
    ["desktop", "desktop:flex-row", "desktop:items-center"],
  ] as const)(
    "stacks full width below %s and becomes a row from it",
    (stackBelow, row, align) => {
      render(
        <Inline stackBelow={stackBelow}>
          <Button variant="secondary">Export</Button>
          <Button>Add batch</Button>
        </Inline>,
      );
      const inline = screen.getByRole("button", {
        name: "Add batch",
      }).parentElement!;
      expect(inline).toHaveAttribute("data-stack-below", stackBelow);
      expect(inline).toHaveClass("flex-col", "items-stretch", row, align);
      expect(inline).not.toHaveClass("items-center");
    },
  );

  it("keeps the DOM (and focus) order of its children", async () => {
    const { container } = render(
      <Inline stackBelow="tablet" aria-label="Page actions">
        <Button variant="secondary">Export</Button>
        <Button>Add batch</Button>
      </Inline>,
    );
    expect(screen.getAllByRole("button").map((b) => b.textContent)).toEqual([
      "Export",
      "Add batch",
    ]);
    await expectNoA11yViolations(container);
  });
});

describe("Grid", () => {
  it("defaults to one column with the 24px panel gap", () => {
    render(
      <Grid>
        <div>Cell</div>
      </Grid>,
    );
    const grid = screen.getByText("Cell").parentElement!;
    expect(grid).toHaveClass("grid", "grid-cols-1", "gap-6", "items-stretch");
    expect(grid).toHaveClass("*:min-w-0");
  });

  it("applies a column count per breakpoint", () => {
    render(
      <Grid columns={{ base: 1, tablet: 2, desktop: 4 }} gap="md" align="start">
        <div>Cell</div>
      </Grid>,
    );
    const grid = screen.getByText("Cell").parentElement!;
    expect(grid).toHaveClass(
      "grid-cols-1",
      "tablet:grid-cols-2",
      "desktop:grid-cols-4",
      "gap-4",
      "items-start",
    );
    expect(grid.className).not.toContain("large:");
  });

  it("spans items across columns, per breakpoint", () => {
    render(
      <Grid columns={{ base: 1, desktop: 12 }}>
        <GridItem span={{ base: "full", desktop: 8 }}>Primary</GridItem>
        <GridItem span={{ base: "full", desktop: 4 }}>Secondary</GridItem>
        <GridItem>Default</GridItem>
      </Grid>,
    );
    expect(screen.getByText("Primary")).toHaveClass(
      "col-span-full",
      "desktop:col-span-8",
      "min-w-0",
    );
    expect(screen.getByText("Secondary")).toHaveClass("desktop:col-span-4");
    expect(screen.getByText("Default")).toHaveClass("col-span-1");
  });

  it("can be a list of cards", async () => {
    const { container } = render(
      <Grid as="ul" columns={{ base: 1, tablet: 3 }} aria-label="Courses">
        <GridItem as="li">Pre-Sea Training</GridItem>
        <GridItem as="li">Marine Engineering</GridItem>
        <GridItem as="li">B.Sc. Nautical Science</GridItem>
      </Grid>,
    );
    const list = screen.getByRole("list", { name: "Courses" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    await expectNoA11yViolations(container);
  });
});

describe("Section", () => {
  it("is a region named by its heading, with description, actions and content", async () => {
    const { container } = render(
      <Section
        title="Upcoming batches"
        description="Batches starting in the next 30 days."
        actions={<Button variant="secondary">View all</Button>}
      >
        <p>DNS 2026-B starts on 5 October.</p>
      </Section>,
    );
    const region = screen.getByRole("region", { name: "Upcoming batches" });
    expect(within(region).getByRole("heading", { level: 2 })).toHaveTextContent(
      "Upcoming batches",
    );
    expect(
      within(region).getByText("Batches starting in the next 30 days."),
    ).toBeInTheDocument();
    expect(
      within(region).getByRole("button", { name: "View all" }),
    ).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("stacks header actions below the title on mobile only", () => {
    render(
      <Section title="Documents" actions={<Button>Upload</Button>}>
        <p>Content</p>
      </Section>,
    );
    const actions = screen.getByRole("button", {
      name: "Upload",
    }).parentElement!;
    expect(actions).toHaveClass("flex-col-reverse", "tablet:flex-row");
    expect(actions.parentElement).toHaveClass("flex-col", "tablet:flex-row");
  });

  it("supports a nested h3 section and custom gap", () => {
    render(
      <Section title="Sea time" titleAs="h3" gap="sm">
        <p>Content</p>
      </Section>,
    );
    const region = screen.getByRole("region", { name: "Sea time" });
    expect(within(region).getByRole("heading", { level: 3 })).toHaveClass(
      "text-card-heading",
    );
    expect(region).toHaveClass("gap-3");
  });

  it("renders a plain grouping element without a title", () => {
    const { container } = render(
      <Section>
        <p>Content</p>
      </Section>,
    );
    expect(screen.queryByRole("region")).toBeNull();
    expect(container.querySelector("section")).toBeNull();
    expect(container.firstElementChild?.tagName).toBe("DIV");
  });

  it("wraps long titles instead of overflowing", () => {
    render(
      <Section title={LONG_NAME}>
        <p>{LONG_EMAIL}</p>
      </Section>,
    );
    expect(screen.getByRole("heading", { name: LONG_NAME })).toHaveClass(
      "break-words",
    );
    expect(screen.getByRole("heading").parentElement).toHaveClass("min-w-0");
  });
});

describe("composition", () => {
  it("composes Container → Stack → Section → Grid without extra landmarks", async () => {
    const { container } = render(
      <Container width="wide">
        <Stack gap="xl">
          <Section title="Summary">
            <Grid columns={{ base: 1, tablet: 2, desktop: 4 }}>
              <div>Enquiries</div>
              <div>Applications</div>
              <div>Admissions</div>
              <div>Fees collected</div>
            </Grid>
          </Section>
          <Section title="Actions">
            <Inline stackBelow="tablet" justify="end">
              <Button variant="secondary">Export</Button>
              <Button>Add enquiry</Button>
            </Inline>
          </Section>
        </Stack>
      </Container>,
    );
    expect(screen.getAllByRole("region")).toHaveLength(2);
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(2);
    await expectNoA11yViolations(container);
  });
});
