import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Button, DropdownMenu } from "@/design-system/components";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

// DropdownMenu `header` (T01-09A): static context above the items that
// describes the menu (the account menu's SESSION-01 identity block).

describe("DropdownMenu header", () => {
  it("renders above the items and describes the menu", async () => {
    const user = userEvent.setup();
    render(
      <DropdownMenu
        trigger={<Button variant="ghost">Account</Button>}
        items={[{ id: "sign-out", label: "Sign out" }]}
        onAction={() => {}}
        header={
          <>
            <p>Ananya Rao</p>
            <p>Roles: Admissions Counsellor</p>
          </>
        }
      />,
    );
    await user.click(screen.getByRole("button", { name: "Account" }));
    const menu = screen.getByRole("menu");
    const header = screen.getByText("Ananya Rao").parentElement!;
    expect(menu).toHaveAttribute("aria-describedby", header.id);
    expect(header.compareDocumentPosition(menu)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    await expectNoA11yViolations(header.parentElement!);
  });

  it("is absent by default", async () => {
    const user = userEvent.setup();
    render(
      <DropdownMenu
        trigger={<Button variant="ghost">Account</Button>}
        items={[{ id: "a", label: "A" }]}
        onAction={() => {}}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Account" }));
    expect(screen.getByRole("menu")).not.toHaveAttribute("aria-describedby");
  });
});
