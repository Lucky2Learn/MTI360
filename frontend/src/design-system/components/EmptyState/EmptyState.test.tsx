import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "@/design-system/components/Button";
import { CompassIcon } from "@/design-system/icons";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("explains what is empty, why, and offers the next action", async () => {
    const { container } = render(
      <EmptyState
        title="No leads yet"
        description="Enquiries from your website and campaigns will appear here."
        primaryAction={<Button>Add lead</Button>}
        secondaryAction={<Button variant="secondary">Import leads</Button>}
      />,
    );

    expect(
      screen.getByRole("heading", { level: 3, name: "No leads yet" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Enquiries from your website/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add lead" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Import leads" }),
    ).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("keeps the icon decorative and accepts a custom icon and heading level", () => {
    const { container } = render(
      <EmptyState
        title="No batches scheduled"
        description="Create a batch to start admissions."
        icon={CompassIcon}
        titleAs="h2"
      />,
    );
    expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
    expect(
      container.querySelector("svg")!.closest("[aria-hidden='true']"),
    ).not.toBeNull();
  });
});
