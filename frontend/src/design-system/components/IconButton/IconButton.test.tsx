import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CloseIcon, SettingsIcon } from "@/design-system/icons";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { IconButton } from "./IconButton";

describe("IconButton", () => {
  it("is named by its required label", async () => {
    const { container } = render(
      <IconButton label="Close panel" icon={CloseIcon} />,
    );
    const button = screen.getByRole("button", { name: "Close panel" });
    expect(button.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    await expectNoA11yViolations(container);
  });

  it("requires a label at compile time", () => {
    // @ts-expect-error — an icon-only button without an accessible name must not compile
    const element = <IconButton icon={SettingsIcon} />;
    expect(element).toBeTruthy();
  });

  it("activates by keyboard", async () => {
    const user = userEvent.setup();
    const onPress = vi.fn();
    render(
      <IconButton
        label="Batch settings"
        icon={SettingsIcon}
        onPress={onPress}
      />,
    );

    await user.tab();
    await user.keyboard("{Enter}");

    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it("uses a square control-height target", () => {
    render(<IconButton label="Close" icon={CloseIcon} size="lg" />);
    expect(screen.getByRole("button").className).toContain("size-control-lg");
  });

  it("keeps its name while pending", async () => {
    const { container } = render(
      <IconButton label="Refresh roster" icon={SettingsIcon} isPending />,
    );
    expect(
      screen.getByRole("button", { name: "Refresh roster" }),
    ).toHaveAttribute("data-pending", "true");
    await expectNoA11yViolations(container);
  });
});
