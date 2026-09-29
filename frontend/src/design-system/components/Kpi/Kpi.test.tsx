import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnchorIcon } from "@/design-system/icons";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Kpi } from "./Kpi";

describe("Kpi", () => {
  it("renders label, value, trend and comparison as a labelled group", async () => {
    const { container } = render(
      <Kpi
        label="Active Students"
        value="1,284"
        trend={{ direction: "up", value: "8.4%", sentiment: "positive" }}
        comparison="vs last month"
        icon={AnchorIcon}
      />,
    );

    const group = screen.getByRole("group", { name: "Active Students" });
    expect(group).toHaveTextContent("1,284");
    expect(group).toHaveTextContent("vs last month");
    await expectNoA11yViolations(container);
  });

  it.each([
    ["up", "Increased by 8.4%"],
    ["down", "Decreased by 3.1%"],
    ["flat", "No change (0.0%)"],
  ] as const)(
    "describes a %s trend in words, not colour",
    (direction, text) => {
      const value =
        direction === "down" ? "3.1%" : direction === "flat" ? "0.0%" : "8.4%";
      render(
        <Kpi label="Placement rate" value="72%" trend={{ direction, value }} />,
      );
      expect(screen.getByText(text)).toHaveClass("sr-only");
    },
  );

  it("colours the trend by the caller's sentiment, not by direction", () => {
    render(
      <Kpi
        label="Overdue fees"
        value="₹4,20,000"
        trend={{ direction: "up", value: "12%", sentiment: "negative" }}
      />,
    );
    const trend = screen.getByText("Increased by 12%").parentElement!;
    expect(trend.className).toContain("text-error-text");
  });

  it("renders optional context", () => {
    render(
      <Kpi
        label="Training berths"
        value="36"
        context="Across 3 partner shipping companies"
      />,
    );
    expect(
      screen.getByText("Across 3 partner shipping companies"),
    ).toBeInTheDocument();
  });

  it("wraps a value wider than a narrow column instead of spilling out (T00-09)", () => {
    render(<Kpi label="Fees collected this year" value="₹12,40,00,000" />);
    expect(screen.getByText("₹12,40,00,000")).toHaveClass("wrap-anywhere");
  });
});
