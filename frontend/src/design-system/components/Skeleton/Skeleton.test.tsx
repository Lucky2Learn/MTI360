import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";

import {
  LoadingRegion,
  Skeleton,
  SkeletonCard,
  SkeletonTableRows,
  SkeletonText,
} from "./Skeleton";

describe("Skeleton", () => {
  it("announces loading once through the region and hides the shapes", async () => {
    const { container } = render(
      <LoadingRegion label="Loading students">
        <SkeletonCard />
        <SkeletonTableRows rows={3} columns={4} />
      </LoadingRegion>,
    );

    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-busy", "true");
    expect(region).toHaveTextContent("Loading students");
    container
      .querySelectorAll("[data-skeleton]")
      .forEach((shape) =>
        expect(shape.closest("[aria-hidden='true']")).not.toBeNull(),
      );
    await expectNoA11yViolations(container);
  });

  it("renders the requested number of text lines and table cells", () => {
    const { container, rerender } = render(<SkeletonText lines={4} />);
    expect(container.querySelectorAll("[data-skeleton]")).toHaveLength(4);
    rerender(<SkeletonTableRows rows={2} columns={3} />);
    expect(container.querySelectorAll("[data-skeleton]")).toHaveLength(6);
  });

  it("pulses only without reduced motion and uses tokens", () => {
    const { container } = render(<Skeleton width="1/2" height="control" />);
    const shape = container.querySelector("[data-skeleton]")!;
    expect(shape.className).toContain("motion-safe:animate-pulse");
    expect(shape.className).toContain("h-control-md");
    expect(shape.className).toContain("bg-border-subtle");
  });
});
