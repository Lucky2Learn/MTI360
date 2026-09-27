import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Card, CardBody, CardFooter, CardHeader } from "./Card";

describe("Card", () => {
  it("renders header, body and footer with a heading", async () => {
    const { container } = render(
      <Card>
        <CardHeader
          title="DNS Batch 2026-B"
          description="Diploma in Nautical Science · 40 cadets"
          actions={<button type="button">Open</button>}
        />
        <CardBody>
          <p>Training berth allocation pending.</p>
        </CardBody>
        <CardFooter>
          <button type="button">View roster</button>
        </CardFooter>
      </Card>,
    );

    expect(
      screen.getByRole("heading", { level: 3, name: "DNS Batch 2026-B" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Training berth allocation pending."),
    ).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("can be a labelled section", async () => {
    const { container } = render(
      <Card as="section" aria-labelledby="fees-title">
        <CardHeader title="Fee summary" titleAs="h2" titleId="fees-title" />
      </Card>,
    );
    expect(
      screen.getByRole("region", { name: "Fee summary" }),
    ).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("applies elevation and padding from tokens", () => {
    const { container } = render(
      <Card elevation="md" padding="lg">
        <p>Content</p>
      </Card>,
    );
    const card = container.firstElementChild!;
    expect(card.className).toContain("shadow-md");
    expect(card.className).toContain("p-6");
    expect(card.className).toContain("bg-surface-primary");
  });
});
