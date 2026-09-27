import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Form } from "@/design-system/components/Field";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Checkbox } from "./Checkbox";

describe("Checkbox", () => {
  it("is a labelled native checkbox and passes axe", async () => {
    const { container } = render(
      <Checkbox description="We'll share batch updates on WhatsApp.">
        Send me WhatsApp updates
      </Checkbox>,
    );
    const checkbox = screen.getByRole("checkbox", {
      name: "Send me WhatsApp updates",
    });
    expect(checkbox).not.toBeChecked();
    expect(checkbox).toHaveAccessibleDescription(
      "We'll share batch updates on WhatsApp.",
    );
    await expectNoA11yViolations(container);
  });

  it("toggles with Space and with a click on the label (uncontrolled)", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Checkbox onChange={onChange}>Hostel required</Checkbox>);
    const checkbox = screen.getByRole("checkbox", { name: "Hostel required" });

    await user.tab();
    await user.keyboard(" ");
    expect(checkbox).toBeChecked();

    await user.click(screen.getByText("Hostel required"));
    expect(checkbox).not.toBeChecked();
    expect(onChange).toHaveBeenNthCalledWith(1, true);
    expect(onChange).toHaveBeenNthCalledWith(2, false);
  });

  it("works controlled", async () => {
    const user = userEvent.setup();
    function Controlled() {
      const [selected, setSelected] = useState(true);
      return (
        <>
          <Checkbox isSelected={selected} onChange={setSelected}>
            Medical fitness verified
          </Checkbox>
          <output>{selected ? "yes" : "no"}</output>
        </>
      );
    }
    render(<Controlled />);
    await user.click(screen.getByRole("checkbox"));
    expect(screen.getByText("no")).toBeInTheDocument();
  });

  it("exposes the indeterminate state as mixed", () => {
    render(<Checkbox isIndeterminate>Select all cadets</Checkbox>);
    const checkbox = screen.getByRole("checkbox", {
      name: "Select all cadets",
    });
    expect((checkbox as HTMLInputElement).indeterminate).toBe(true);
  });

  it("is required with an error message, and submits its value", async () => {
    const user = userEvent.setup();
    let submitted: FormData | undefined;
    render(
      <Form
        onSubmit={(event) => {
          event.preventDefault();
          submitted = new FormData(event.currentTarget);
        }}
      >
        <Checkbox
          name="consent"
          value="yes"
          isRequired
          errorMessage="Consent is required to continue."
        >
          I agree to be contacted about admissions
        </Checkbox>
        <button type="submit">Submit</button>
      </Form>,
    );
    await user.click(screen.getByRole("button", { name: "Submit" }));
    expect(submitted).toBeUndefined();
    expect(
      screen.getByText("Consent is required to continue."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Submit" }));
    expect(submitted?.get("consent")).toBe("yes");
  });

  it("can be disabled", () => {
    render(<Checkbox isDisabled>Scholarship applied</Checkbox>);
    expect(screen.getByRole("checkbox")).toBeDisabled();
  });
});
