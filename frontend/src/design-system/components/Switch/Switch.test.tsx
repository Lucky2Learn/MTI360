import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Switch } from "./Switch";

describe("Switch", () => {
  it("is a labelled switch with a description and passes axe", async () => {
    const { container } = render(
      <Switch description="Applies to all new records.">
        Email notifications
      </Switch>,
    );
    const toggle = screen.getByRole("switch", { name: "Email notifications" });
    expect(toggle).not.toBeChecked();
    expect(toggle).toHaveAccessibleDescription("Applies to all new records.");
    await expectNoA11yViolations(container);
  });

  it("toggles with Space and click (uncontrolled)", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Switch onChange={onChange}>Compact rows</Switch>);
    await user.tab();
    await user.keyboard(" ");
    expect(screen.getByRole("switch")).toBeChecked();
    await user.click(screen.getByText("Compact rows"));
    expect(onChange).toHaveBeenNthCalledWith(1, true);
    expect(onChange).toHaveBeenNthCalledWith(2, false);
  });

  it("works controlled and shows state with a mark, not colour alone", async () => {
    const user = userEvent.setup();
    function Controlled() {
      const [on, setOn] = useState(true);
      return (
        <Switch isSelected={on} onChange={setOn}>
          Auto-save drafts
        </Switch>
      );
    }
    const { container } = render(<Controlled />);
    expect(container.querySelector("svg")).not.toBeNull();
    await user.click(screen.getByRole("switch"));
    expect(screen.getByRole("switch")).not.toBeChecked();
    expect(container.querySelector("svg")).toBeNull();
  });

  it("links an error message when invalid and can be disabled", () => {
    render(
      <>
        <Switch isInvalid errorMessage="Enable this to continue.">
          Accept data retention policy
        </Switch>
        <Switch isDisabled>Beta features</Switch>
      </>,
    );
    expect(
      screen.getByRole("switch", { name: "Accept data retention policy" }),
    ).toHaveAccessibleDescription("Enable this to continue.");
    expect(
      screen.getByRole("switch", { name: "Beta features" }),
    ).toBeDisabled();
  });
});
