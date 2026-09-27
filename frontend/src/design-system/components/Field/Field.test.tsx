import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Input, TextField } from "react-aria-components";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";

import {
  FieldDescription,
  FieldErrorMessage,
  FieldLabel,
  FieldSuccessMessage,
  Form,
} from "./Field";

// The Field pieces are composed by Input, Textarea, Select, … ; here they are
// exercised with a bare React Aria TextField.
function NameField(props: { isRequired?: boolean; errorMessage?: string }) {
  return (
    <TextField name="fullName" isRequired={props.isRequired}>
      <FieldLabel isRequired={props.isRequired}>Full name</FieldLabel>
      <Input />
      <FieldDescription>As printed on the CDC.</FieldDescription>
      <FieldErrorMessage>{props.errorMessage}</FieldErrorMessage>
    </TextField>
  );
}

describe("Field foundation", () => {
  it("labels the control and links the description", async () => {
    const { container } = render(<NameField />);
    const input = screen.getByRole("textbox", { name: "Full name" });
    expect(input).toHaveAccessibleDescription("As printed on the CDC.");
    await expectNoA11yViolations(container);
  });

  it("shows a visible required indicator hidden from assistive technology", () => {
    render(<NameField isRequired />);
    const input = screen.getByRole("textbox", { name: "Full name" });
    expect(input).toBeRequired();
    const star = screen.getByText("*");
    expect(star).toHaveAttribute("aria-hidden", "true");
  });

  it("blocks an invalid submit, shows icon + text and focuses the first invalid field", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn((event: SubmitEvent) => event.preventDefault());
    const { container } = render(
      <Form onSubmit={(event) => onSubmit(event.nativeEvent as SubmitEvent)}>
        <NameField isRequired errorMessage="Enter the cadet's full name." />
        <button type="submit">Save</button>
      </Form>,
    );

    await user.click(screen.getByRole("button", { name: "Save" }));

    const input = screen.getByRole("textbox", { name: "Full name" });
    expect(onSubmit).not.toHaveBeenCalled();
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveFocus();
    expect(input).toHaveAccessibleDescription(
      expect.stringContaining("Enter the cadet's full name."),
    );
    expect(container.querySelector(".text-error-text svg")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
    await expectNoA11yViolations(container);
  });

  it("maps server validation errors to fields by name and clears them once edited", async () => {
    const user = userEvent.setup();
    render(
      <Form validationErrors={{ fullName: "This name is already registered." }}>
        <NameField />
      </Form>,
    );

    const input = screen.getByRole("textbox", { name: "Full name" });
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(
      screen.getByText("This name is already registered."),
    ).toBeInTheDocument();

    await user.type(input, "Arjun Menon");
    await user.tab(); // native validation updates on commit (blur)

    expect(input).not.toHaveAttribute("aria-invalid");
    expect(screen.queryByText("This name is already registered.")).toBeNull();
  });

  it("renders an opt-in success message with an icon", () => {
    const { container } = render(
      <FieldSuccessMessage id="ok">Email verified.</FieldSuccessMessage>,
    );
    expect(screen.getByText("Email verified.")).toBeInTheDocument();
    expect(container.querySelector("svg")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });
});
