import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Form } from "@/design-system/components/Field";
import { AnchorIcon } from "@/design-system/icons";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Input } from "./Input";

describe("Input", () => {
  it("is labelled, described and passes axe", async () => {
    const { container } = render(
      <Input
        label="Email"
        type="email"
        description="We send the admission letter here."
      />,
    );
    const input = screen.getByRole("textbox", { name: "Email" });
    expect(input).toHaveAttribute("type", "email");
    expect(input).toHaveAccessibleDescription(
      "We send the admission letter here.",
    );
    await expectNoA11yViolations(container);
  });

  it("works uncontrolled with defaultValue", async () => {
    const user = userEvent.setup();
    render(<Input label="Full name" defaultValue="Arjun" />);
    const input = screen.getByRole("textbox", { name: "Full name" });
    await user.type(input, " Menon");
    expect(input).toHaveValue("Arjun Menon");
  });

  it("works controlled with value and onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    function Controlled() {
      const [value, setValue] = useState("");
      return (
        <Input
          label="Mobile"
          type="tel"
          value={value}
          onChange={(next) => {
            onChange(next);
            setValue(next.replace(/\D/g, ""));
          }}
        />
      );
    }
    render(<Controlled />);
    await user.type(screen.getByRole("textbox", { name: "Mobile" }), "98-20");
    expect(onChange).toHaveBeenLastCalledWith("9820");
    expect(screen.getByRole("textbox", { name: "Mobile" })).toHaveValue("9820");
  });

  it("submits its value under its name", async () => {
    const user = userEvent.setup();
    let submitted: FormData | undefined;
    render(
      <Form
        onSubmit={(event) => {
          event.preventDefault();
          submitted = new FormData(event.currentTarget);
        }}
      >
        <Input label="Full name" name="fullName" defaultValue="Arjun Menon" />
        <button type="submit">Save</button>
      </Form>,
    );
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submitted?.get("fullName")).toBe("Arjun Menon");
  });

  it("validates type=email natively and shows the custom message", async () => {
    const user = userEvent.setup();
    render(
      <Form onSubmit={(event) => event.preventDefault()}>
        <Input
          label="Email"
          name="email"
          type="email"
          isRequired
          errorMessage="Enter a valid email address, e.g. name@institute.in."
        />
        <button type="submit">Save</button>
      </Form>,
    );
    const input = screen.getByRole("textbox", { name: "Email" });
    await user.type(input, "not-an-email");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveFocus();
    expect(input).toHaveAccessibleDescription(
      expect.stringContaining("Enter a valid email address"),
    );
  });

  it("supports a custom validate function", async () => {
    const user = userEvent.setup();
    render(
      <Form onSubmit={(event) => event.preventDefault()}>
        <Input
          label="CDC number"
          name="cdc"
          validate={(value) =>
            /^[A-Z]{3}\d{6}$/.test(value) ? null : "Use the format MUM123456."
          }
        />
        <button type="submit">Save</button>
      </Form>,
    );
    await user.type(screen.getByRole("textbox", { name: "CDC number" }), "123");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText("Use the format MUM123456.")).toBeInTheDocument();
  });

  it("shows an explicit invalid state with icon + text", async () => {
    const { container } = render(
      <Input
        label="Passport number"
        isInvalid
        errorMessage="Passport number is already used."
      />,
    );
    const input = screen.getByRole("textbox", { name: "Passport number" });
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(
      screen.getByText("Passport number is already used."),
    ).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("shows an opt-in success message linked to the input", () => {
    render(<Input label="Email" successMessage="Email verified." />);
    expect(
      screen.getByRole("textbox", { name: "Email" }),
    ).toHaveAccessibleDescription("Email verified.");
  });

  it("supports disabled and read-only states", () => {
    render(
      <>
        <Input label="Institute code" isReadOnly defaultValue="MTI-MUM-01" />
        <Input label="Campus" isDisabled defaultValue="Mumbai" />
      </>,
    );
    expect(
      screen.getByRole("textbox", { name: "Institute code" }),
    ).toHaveAttribute("readonly");
    expect(screen.getByRole("textbox", { name: "Campus" })).toBeDisabled();
  });

  it("renders a decorative leading icon", () => {
    const { container } = render(<Input label="Port" icon={AnchorIcon} />);
    expect(container.querySelector("svg")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });
});
