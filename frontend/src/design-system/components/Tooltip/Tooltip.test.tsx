import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { IconButton } from "@/design-system/components/IconButton";
import { SettingsIcon } from "@/design-system/icons";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Tooltip } from "./Tooltip";

function Settings() {
  return (
    <Tooltip content="Batch settings" delay={50}>
      <IconButton label="Batch settings" icon={SettingsIcon} />
    </Tooltip>
  );
}

describe("Tooltip", () => {
  it("shows on keyboard focus, describes the trigger and passes axe", async () => {
    const user = userEvent.setup();
    render(<Settings />);
    await user.tab();

    const tooltip = await screen.findByRole("tooltip");
    expect(tooltip).toHaveTextContent("Batch settings");
    expect(
      screen.getByRole("button", { name: "Batch settings" }),
    ).toHaveAttribute("aria-describedby", tooltip.id);
    await expectNoA11yViolations(document.body);
  });

  it("hides on Escape", async () => {
    const user = userEvent.setup();
    render(<Settings />);
    await user.tab();
    await screen.findByRole("tooltip");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("tooltip")).toBeNull());
  });

  // Pointer hover depends on React Aria's global pointer-modality tracking,
  // which jsdom does not reproduce; hover show/hide is verified in Chromium
  // (T00-07C browser verification).

  it("does not replace the trigger's accessible name", () => {
    render(<Settings />);
    expect(
      screen.getByRole("button", { name: "Batch settings" }),
    ).toBeInTheDocument();
  });

  it("can be disabled", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Hidden" isDisabled delay={0}>
        <IconButton label="Settings" icon={SettingsIcon} />
      </Tooltip>,
    );
    await user.tab();
    expect(screen.queryByRole("tooltip")).toBeNull();
  });
});
