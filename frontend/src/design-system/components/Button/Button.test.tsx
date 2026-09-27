import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AddIcon, DownloadIcon } from "@/design-system/icons";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Button, type ButtonVariant } from "./Button";

const VARIANTS: ButtonVariant[] = [
  "primary",
  "secondary",
  "tertiary",
  "ghost",
  "destructive",
  "success",
];

describe("Button", () => {
  it.each(VARIANTS)(
    "renders the %s variant as an accessible button",
    async (variant) => {
      const { container } = render(
        <Button variant={variant}>Enrol cadet</Button>,
      );
      expect(
        screen.getByRole("button", { name: "Enrol cadet" }),
      ).toBeInTheDocument();
      await expectNoA11yViolations(container);
    },
  );

  it("activates with pointer, Enter and Space", async () => {
    const user = userEvent.setup();
    const onPress = vi.fn();
    render(<Button onPress={onPress}>Save batch</Button>);

    await user.click(screen.getByRole("button", { name: "Save batch" }));
    await user.keyboard("{Enter}");
    await user.keyboard(" ");

    expect(onPress).toHaveBeenCalledTimes(3);
  });

  it("is reachable by keyboard and exposes focus-visible state", async () => {
    const user = userEvent.setup();
    render(<Button>Publish course</Button>);

    await user.tab();

    const button = screen.getByRole("button", { name: "Publish course" });
    expect(button).toHaveFocus();
    expect(button).toHaveAttribute("data-focus-visible", "true");
  });

  it("does not activate when disabled", async () => {
    const user = userEvent.setup();
    const onPress = vi.fn();
    render(
      <Button isDisabled onPress={onPress}>
        Approve
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Approve" });
    await user.click(button);

    expect(button).toBeDisabled();
    expect(onPress).not.toHaveBeenCalled();
  });

  it("keeps its name, shows pending state and blocks presses while loading", async () => {
    const user = userEvent.setup();
    const onPress = vi.fn();
    const { container } = render(
      <Button isPending onPress={onPress} iconStart={DownloadIcon}>
        Export roster
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Export roster" });
    await user.click(button);

    expect(button).toHaveAttribute("data-pending", "true");
    expect(onPress).not.toHaveBeenCalled();
    await expectNoA11yViolations(container);
  });

  it("renders decorative icons hidden from assistive technology", () => {
    render(
      <Button iconStart={AddIcon} iconEnd={DownloadIcon}>
        Add batch
      </Button>,
    );
    const icons = screen.getByRole("button").querySelectorAll("svg");
    expect(icons).toHaveLength(2);
    icons.forEach((icon) =>
      expect(icon).toHaveAttribute("aria-hidden", "true"),
    );
  });

  it("renders a link when given href, with safe rel for new tabs", async () => {
    const { container } = render(
      <Button
        href="https://example.org/stcw"
        target="_blank"
        variant="secondary"
      >
        STCW overview
      </Button>,
    );
    const link = screen.getByRole("link", { name: "STCW overview" });
    expect(link).toHaveAttribute("href", "https://example.org/stcw");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    await expectNoA11yViolations(container);
  });

  it("uses only design tokens for its styling", () => {
    render(<Button variant="success">Record payment</Button>);
    const button = screen.getByRole("button");
    expect(button.className).toContain("bg-success-strong");
    expect(button.className).toContain("text-text-inverse");
    expect(button.className).toContain("h-control-md");
  });
});
