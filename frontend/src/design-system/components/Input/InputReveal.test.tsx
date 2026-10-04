import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Button, Form, Input } from "@/design-system/components";
import { expectFocusRing } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

// Revealable password (T01-09A; T01-04 UI contract §13, S15).

function PasswordForm() {
  return (
    <Form onSubmit={(event) => event.preventDefault()}>
      <Input label="Password" name="password" type="password" isRevealable />
      <Button type="submit">Sign in</Button>
    </Form>
  );
}

describe("Input isRevealable", () => {
  it("is a named toggle controlling the input; hidden by default", async () => {
    const { container } = render(<PasswordForm />);
    const input = screen.getByLabelText("Password");
    const toggle = screen.getByRole("button", { name: "Show password" });
    expect(input).toHaveAttribute("type", "password");
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    expect(toggle).toHaveAttribute("aria-controls", input.id);
    expectFocusRing(toggle);
    await expectNoA11yViolations(container);
  });

  it("reveals and hides, keeping the value and the focus on the toggle", async () => {
    const user = userEvent.setup({ delay: null });
    render(<PasswordForm />);
    const input = screen.getByLabelText("Password");
    await user.type(input, "Lighthouse-Keeper-77");
    await user.click(screen.getByRole("button", { name: "Show password" }));
    const toggle = screen.getByRole("button", { name: "Hide password" });
    expect(input).toHaveAttribute("type", "text");
    expect(input).toHaveValue("Lighthouse-Keeper-77");
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(toggle).toHaveFocus();
    await user.keyboard(" ");
    expect(input).toHaveAttribute("type", "password");
  });

  it("hides the value again when the form is submitted", async () => {
    const user = userEvent.setup({ delay: null });
    render(<PasswordForm />);
    await user.click(screen.getByRole("button", { name: "Show password" }));
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "type",
      "password",
    );
  });

  it("is never offered for other input types", () => {
    render(<Input label="Email" type="email" isRevealable />);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("forwards autoCapitalize to the input", () => {
    render(<Input label="Email" type="email" autoCapitalize="none" />);
    expect(screen.getByLabelText("Email")).toHaveAttribute(
      "autocapitalize",
      "none",
    );
  });
});
