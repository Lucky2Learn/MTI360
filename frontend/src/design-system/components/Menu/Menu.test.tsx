import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "@/design-system/components/Button";
import { IconButton } from "@/design-system/components/IconButton";
import {
  CopyIcon,
  DeleteIcon,
  EditIcon,
  MoreIcon,
  ViewIcon,
} from "@/design-system/icons";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { ContextMenu } from "./ContextMenu";
import { DropdownMenu } from "./DropdownMenu";

import type { MenuEntry } from "./MenuContent";

const ITEMS: MenuEntry[] = [
  { id: "view", label: "View", icon: ViewIcon },
  { id: "edit", label: "Edit", icon: EditIcon },
  { id: "duplicate", label: "Duplicate", icon: CopyIcon, isDisabled: true },
  { id: "sep", type: "separator" },
  { id: "delete", label: "Delete", icon: DeleteIcon, tone: "destructive" },
];

function RowActions({ onAction }: { onAction: (id: string) => void }) {
  return (
    <DropdownMenu
      trigger={<IconButton label="More actions" icon={MoreIcon} />}
      items={ITEMS}
      onAction={onAction}
    />
  );
}

describe("DropdownMenu", () => {
  it("opens from the keyboard onto the first item and passes axe", async () => {
    const user = userEvent.setup();
    render(<RowActions onAction={vi.fn()} />);
    const trigger = screen.getByRole("button", { name: "More actions" });
    expect(trigger).toHaveAttribute("aria-haspopup", "true");

    await user.tab();
    await user.keyboard("{Enter}");

    // Labelled by its trigger (menu-button pattern).
    const menu = screen.getByRole("menu", { name: "More actions" });
    expect(within(menu).getAllByRole("menuitem")).toHaveLength(4);
    expect(within(menu).getByRole("separator")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("menuitem", { name: "View" })).toHaveFocus(),
    );
    await expectNoA11yViolations(document.body);
  });

  it("moves with arrows, skips disabled items and activates with Enter", async () => {
    const user = userEvent.setup();
    const onAction = vi.fn();
    render(<RowActions onAction={onAction} />);
    await user.tab();
    await user.keyboard("{Enter}"); // keyboard open focuses the first item
    await waitFor(() =>
      expect(screen.getByRole("menuitem", { name: "View" })).toHaveFocus(),
    );

    await user.keyboard("{ArrowDown}{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Delete" })).toHaveFocus();
    expect(screen.getByRole("menuitem", { name: "Duplicate" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    await user.keyboard("{Enter}");
    expect(onAction).toHaveBeenCalledWith("delete");
    await waitFor(() => expect(screen.queryByRole("menu")).toBeNull());
  });

  it("closes with Escape and returns focus to the trigger", async () => {
    const user = userEvent.setup();
    render(<RowActions onAction={vi.fn()} />);
    const trigger = screen.getByRole("button", { name: "More actions" });
    await user.click(trigger);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("menu")).toBeNull());
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("marks destructive items with an error icon and error text on focus", async () => {
    const user = userEvent.setup();
    render(<RowActions onAction={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "More actions" }));
    const del = screen.getByRole("menuitem", { name: "Delete" });
    // Label stays text-primary at rest (Dark error-text on surface-elevated
    // is below 4.5:1); error-text only on the error-surface focus background.
    expect(del).toHaveClass(
      "text-text-primary",
      "data-focused:bg-error-surface",
      "data-focused:text-error-text",
    );
    const icon = del.querySelector("svg");
    expect(icon).toHaveAttribute("aria-hidden", "true");
    expect(icon).toHaveClass("text-error");
  });
});

function Document() {
  return (
    <ContextMenu label="Document actions" items={ITEMS} onAction={onDocAction}>
      <Button variant="secondary">Medical certificate.pdf</Button>
    </ContextMenu>
  );
}
const onDocAction = vi.fn<(id: string) => void>();

describe("ContextMenu", () => {
  it("opens on right-click with focus on the first item and passes axe", async () => {
    render(<Document />);
    fireEvent.contextMenu(
      screen.getByRole("button", { name: "Medical certificate.pdf" }),
      {
        clientX: 40,
        clientY: 60,
      },
    );
    expect(
      screen.getByRole("menu", { name: "Document actions" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("menuitem", { name: "View" })).toHaveFocus(),
    );
    await expectNoA11yViolations(document.body);
  });

  it("opens with Shift+F10, runs the action and restores focus", async () => {
    const user = userEvent.setup();
    onDocAction.mockClear();
    render(<Document />);
    const target = screen.getByRole("button", {
      name: "Medical certificate.pdf",
    });
    await user.tab();
    expect(target).toHaveFocus();

    await user.keyboard("{Shift>}{F10}{/Shift}");
    await waitFor(() =>
      expect(screen.getByRole("menuitem", { name: "View" })).toHaveFocus(),
    );
    await user.keyboard("{ArrowDown}{Enter}");

    expect(onDocAction).toHaveBeenCalledWith("edit");
    await waitFor(() => expect(screen.queryByRole("menu")).toBeNull());
    await waitFor(() => expect(target).toHaveFocus());
  });

  it("closes with Escape and restores focus", async () => {
    const user = userEvent.setup();
    render(<Document />);
    const target = screen.getByRole("button", {
      name: "Medical certificate.pdf",
    });
    await user.tab();
    await user.keyboard("{ContextMenu}");
    await screen.findByRole("menu");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("menu")).toBeNull());
    await waitFor(() => expect(target).toHaveFocus());
  });
});
