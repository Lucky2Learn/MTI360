import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnchorIcon } from "@/design-system/icons";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Badge, type BadgeTone } from "./Badge";

const TONES: [BadgeTone, string][] = [
  ["neutral", "Draft"],
  ["info", "Pending"],
  ["success", "Approved"],
  ["warning", "Overdue"],
  ["error", "Rejected"],
  ["ai", "AI suggested"],
];

describe("Badge", () => {
  it.each(TONES)("%s badge shows its status as text", async (tone, label) => {
    const { container } = render(<Badge tone={tone}>{label}</Badge>);
    expect(screen.getByText(label)).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it.each(TONES.filter(([tone]) => tone !== "neutral"))(
    "%s badge adds a decorative icon (status is never colour alone)",
    (tone, label) => {
      const { container } = render(<Badge tone={tone}>{label}</Badge>);
      const icon = container.querySelector("svg");
      expect(icon).not.toBeNull();
      expect(icon).toHaveAttribute("aria-hidden", "true");
    },
  );

  it("supports a custom icon or no icon", () => {
    const { container, rerender } = render(
      <Badge icon={AnchorIcon}>Deck Cadet</Badge>,
    );
    expect(container.querySelector("svg")).not.toBeNull();
    rerender(
      <Badge tone="success" icon={false}>
        Active
      </Badge>,
    );
    expect(container.querySelector("svg")).toBeNull();
  });

  it("uses the tone text token, not the indicator colour, for text", () => {
    const { container } = render(<Badge tone="warning">Overdue</Badge>);
    expect(container.firstElementChild!.className).toContain(
      "text-warning-text",
    );
  });
});
