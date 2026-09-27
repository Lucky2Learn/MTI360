import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Alert, type AlertTone } from "./Alert";

describe("Alert", () => {
  it.each<[AlertTone, string]>([
    ["info", "status"],
    ["success", "status"],
    ["warning", "status"],
    ["error", "alert"],
  ])("%s alert uses role=%s", async (tone, role) => {
    const { container } = render(
      <Alert tone={tone} title="Payment recorded successfully.">
        Receipt MTI-2026-0412 was sent to the cadet.
      </Alert>,
    );
    expect(screen.getByRole(role)).toHaveTextContent(
      "Payment recorded successfully.",
    );
    await expectNoA11yViolations(container);
  });

  it("pairs every tone with an icon shape (not colour alone)", () => {
    const { container } = render(
      <Alert tone="warning" title="Medical certificate expires in 14 days" />,
    );
    const icon = container.querySelector("svg");
    expect(icon).toHaveAttribute("aria-hidden", "true");
    expect(container.firstElementChild!.className).toContain(
      "text-warning-text",
    );
  });

  it("renders an optional action", () => {
    render(
      <Alert
        tone="info"
        title="New RPSL circular"
        action={<a href="#circular">Read circular</a>}
      />,
    );
    expect(
      screen.getByRole("link", { name: "Read circular" }),
    ).toBeInTheDocument();
  });
});
