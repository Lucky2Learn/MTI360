import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Form } from "@/design-system/components/Field";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { RadioGroup, type RadioOption } from "./RadioGroup";

const MODES: RadioOption[] = [
  { value: "classroom", label: "Classroom", description: "On campus" },
  { value: "online", label: "Online" },
  { value: "hybrid", label: "Hybrid" },
  { value: "simulator", label: "Simulator", isDisabled: true },
];

describe("RadioGroup", () => {
  it("is a labelled radiogroup and passes axe", async () => {
    const { container } = render(
      <RadioGroup label="Delivery mode" options={MODES} />,
    );
    expect(
      screen.getByRole("radiogroup", { name: "Delivery mode" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(4);
    await expectNoA11yViolations(container);
  });

  it("uses one Tab stop and arrow keys, skipping disabled options", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <RadioGroup
        label="Delivery mode"
        options={MODES}
        defaultValue="online"
        onChange={onChange}
      />,
    );
    await user.tab();
    expect(screen.getByRole("radio", { name: "Online" })).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(onChange).toHaveBeenLastCalledWith("hybrid");
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("radio", { name: /Classroom/ })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Simulator" })).toBeDisabled();
  });

  it("works controlled and horizontal", async () => {
    const user = userEvent.setup();
    function Controlled() {
      const [value, setValue] = useState("classroom");
      return (
        <>
          <RadioGroup
            label="Mode"
            options={MODES}
            orientation="horizontal"
            value={value}
            onChange={setValue}
          />
          <output>{value}</output>
        </>
      );
    }
    render(<Controlled />);
    expect(screen.getByRole("radiogroup")).toHaveAttribute(
      "aria-orientation",
      "horizontal",
    );
    await user.click(screen.getByRole("radio", { name: "Online" }));
    expect(
      screen.getByText("online", { selector: "output" }),
    ).toBeInTheDocument();
  });

  it("is required with an error and submits under its name", async () => {
    const user = userEvent.setup();
    let submitted: FormData | undefined;
    render(
      <Form
        onSubmit={(event) => {
          event.preventDefault();
          submitted = new FormData(event.currentTarget);
        }}
      >
        <RadioGroup
          label="Mode"
          name="mode"
          options={MODES}
          isRequired
          errorMessage="Choose a delivery mode."
        />
        <button type="submit">Save</button>
      </Form>,
    );
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submitted).toBeUndefined();
    expect(screen.getByText("Choose a delivery mode.")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Hybrid" }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submitted?.get("mode")).toBe("hybrid");
  });
});
