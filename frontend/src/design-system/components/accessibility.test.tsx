import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SettingsIcon } from "@/design-system/icons";
import {
  expectFocusContained,
  expectFocusRing,
  expectNamedControls,
} from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import {
  AlertDialog,
  Button,
  Checkbox,
  DatePicker,
  Dialog,
  Drawer,
  DropdownMenu,
  Form,
  IconButton,
  Input,
  Popover,
  RadioGroup,
  Search,
  Select,
  Switch,
  Textarea,
  TimePicker,
  Tooltip,
} from "./index";

import type { ReactElement } from "react";

// Cross-component accessibility contract (T00-10; docs/architecture/
// accessibility.md). One table per interaction model so a regression in any
// component shows up here: names, focus ring styling, keyboard operation,
// overlay focus entry / containment / Escape / focus return, semantics.
// Per-component details stay in each component's own tests.

const PORTS = [
  { id: "mum", label: "Mumbai" },
  { id: "koc", label: "Kochi" },
];

type OverlayCase = {
  name: string;
  trigger: string | RegExp;
  role: "dialog" | "alertdialog" | "menu" | "listbox";
  /** Focus must stay inside while open (modal overlays). */
  modal: boolean;
  element: () => ReactElement;
};

const OVERLAYS: OverlayCase[] = [
  {
    name: "Dialog",
    trigger: "Edit vessel",
    role: "dialog",
    modal: true,
    element: () => (
      <Dialog
        title="Edit vessel"
        description="Update the vessel particulars."
        trigger={<Button>Edit vessel</Button>}
        actions={(close) => <Button onPress={close}>Save</Button>}
      >
        <Input label="Call sign" />
      </Dialog>
    ),
  },
  {
    name: "AlertDialog",
    trigger: "Delete record",
    role: "alertdialog",
    modal: true,
    element: () => (
      <AlertDialog
        title="Delete this record?"
        description="This cannot be undone."
        confirmLabel="Delete"
        tone="destructive"
        onConfirm={vi.fn()}
        trigger={<Button variant="destructive">Delete record</Button>}
      />
    ),
  },
  {
    name: "Drawer",
    trigger: "Open details",
    role: "dialog",
    modal: true,
    element: () => (
      <Drawer
        title="Batch details"
        trigger={<Button>Open details</Button>}
        actions={(close) => <Button onPress={close}>Done</Button>}
      >
        <Input label="Reference" />
      </Drawer>
    ),
  },
  {
    name: "Popover",
    trigger: "What is DWT?",
    role: "dialog",
    modal: true,
    element: () => (
      <Popover
        title="Deadweight tonnage"
        trigger={<Button variant="secondary">What is DWT?</Button>}
      >
        The weight a vessel can carry.
      </Popover>
    ),
  },
  {
    name: "DropdownMenu",
    trigger: "Row actions",
    role: "menu",
    modal: false,
    element: () => (
      <DropdownMenu
        trigger={<IconButton label="Row actions" icon={SettingsIcon} />}
        items={[
          { id: "view", label: "View" },
          { id: "edit", label: "Edit" },
          { id: "archive", label: "Archive", isDisabled: true },
          { id: "delete", label: "Delete", tone: "destructive" },
        ]}
        onAction={vi.fn()}
      />
    ),
  },
  {
    name: "Select",
    trigger: /Home port/,
    role: "listbox",
    modal: false,
    element: () => <Select label="Home port" options={PORTS} />,
  },
];

describe("overlay keyboard contract (T00-10)", () => {
  it.each(OVERLAYS)(
    "$name opens from the keyboard, takes focus, closes with Escape and returns focus",
    async ({ trigger, role, modal, element }) => {
      const user = userEvent.setup();
      render(
        <>
          <Button>Before</Button>
          {element()}
        </>,
      );
      await user.tab();
      await user.tab();
      const opener = screen.getByRole("button", { name: trigger });
      expect(opener).toHaveFocus();
      expectFocusRing(opener);

      await user.keyboard("{Enter}");
      const overlay = await screen.findByRole(role);
      await waitFor(() =>
        expect(overlay.contains(document.activeElement)).toBe(true),
      );
      expectNamedControls(overlay);
      await expectNoA11yViolations(document.body);
      if (modal) await expectFocusContained(user, overlay, 6);

      await user.keyboard("{Escape}");
      await waitFor(() => expect(screen.queryByRole(role)).toBeNull());
      await waitFor(() => expect(opener).toHaveFocus());
    },
  );

  it("AlertDialog is distinct from Dialog and focuses the safe action", async () => {
    const user = userEvent.setup();
    render(OVERLAYS[1]!.element());
    await user.click(screen.getByRole("button", { name: "Delete record" }));
    const alert = await screen.findByRole("alertdialog", {
      name: "Delete this record?",
    });
    expect(alert).toHaveAccessibleDescription("This cannot be undone.");
    await waitFor(() =>
      expect(
        within(alert).getByRole("button", { name: "Cancel" }),
      ).toHaveFocus(),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("menus expose item names, disabled state and the Home/End keys", async () => {
    const user = userEvent.setup();
    render(OVERLAYS[4]!.element());
    screen.getByRole("button", { name: "Row actions" }).focus();
    await user.keyboard("{Enter}");
    const menu = await screen.findByRole("menu");
    const items = within(menu).getAllByRole("menuitem");
    expect(items.map((item) => item.textContent)).toEqual([
      "View",
      "Edit",
      "Archive",
      "Delete",
    ]);
    expect(
      within(menu).getByRole("menuitem", { name: "Archive" }),
    ).toHaveAttribute("aria-disabled", "true");
    await user.keyboard("{End}");
    expect(
      within(menu).getByRole("menuitem", { name: "Delete" }),
    ).toHaveFocus();
    await user.keyboard("{Home}");
    expect(within(menu).getByRole("menuitem", { name: "View" })).toHaveFocus();
  });

  it("Tooltip shows on keyboard focus, describes its trigger and hides on Escape", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Open settings">
        <IconButton label="Settings" icon={SettingsIcon} />
      </Tooltip>,
    );
    await user.tab();
    const trigger = screen.getByRole("button", { name: "Settings" });
    expect(trigger).toHaveFocus();
    const tooltip = await screen.findByRole("tooltip");
    expect(tooltip).toHaveTextContent("Open settings");
    expect(trigger).toHaveAccessibleDescription("Open settings");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("tooltip")).toBeNull());
    expect(trigger).toHaveFocus();
  });
});

function Controls() {
  return (
    <form aria-label="Controls">
      <Input label="Full name" isRequired />
      <Textarea label="Notes" maxLength={200} showCount />
      <Search label="Search cadets" />
      <Checkbox>I agree to be contacted</Checkbox>
      <Switch>Email notifications</Switch>
      <RadioGroup
        label="Mode"
        options={[
          { value: "classroom", label: "Classroom" },
          { value: "online", label: "Online" },
        ]}
        defaultValue="classroom"
      />
      <DatePicker label="Date of birth" />
      <TimePicker label="Session starts" />
      <Button>Submit</Button>
      <Button isDisabled>Unavailable</Button>
      <IconButton label="Settings" icon={SettingsIcon} />
    </form>
  );
}

describe("control contract (T00-10)", () => {
  it("names every control, passes axe and uses the token focus ring", async () => {
    const { container } = render(<Controls />);
    expectNamedControls(container);
    await expectNoA11yViolations(container);
    for (const element of container.querySelectorAll<HTMLElement>(
      "button:not([tabindex='-1']), input:not([type=hidden]):not([hidden]), textarea, [role=spinbutton]",
    )) {
      if (element.closest("[aria-hidden=true]")) continue;
      expectFocusRing(element);
    }
  });

  it("communicates required, disabled and checked state semantically, not by colour", () => {
    render(<Controls />);
    expect(screen.getByRole("textbox", { name: /Full name/ })).toBeRequired();
    expect(screen.getByRole("button", { name: "Unavailable" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Classroom" })).toBeChecked();
    expect(
      screen.getByRole("switch", { name: "Email notifications" }),
    ).not.toBeChecked();
    expect(
      screen.getByRole("textbox", { name: "Notes" }),
    ).toHaveAccessibleDescription(/0 \/ 200/);
  });

  it("operates checkbox, switch and radio group with the keyboard", async () => {
    const user = userEvent.setup();
    render(<Controls />);
    const checkbox = screen.getByRole("checkbox", {
      name: "I agree to be contacted",
    });
    checkbox.focus();
    await user.keyboard(" ");
    expect(checkbox).toBeChecked();

    const toggle = screen.getByRole("switch", { name: "Email notifications" });
    toggle.focus();
    await user.keyboard(" ");
    expect(toggle).toBeChecked();

    screen.getByRole("radio", { name: "Classroom" }).focus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("radio", { name: "Online" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Online" })).toHaveFocus();
  });

  it("links a validation error to its field and marks it invalid", async () => {
    const user = userEvent.setup();
    render(
      <Form aria-label="Enquiry">
        <Input
          label="Email"
          type="email"
          isRequired
          errorMessage="Enter an email address."
        />
        <Button type="submit">Send</Button>
      </Form>,
    );
    await user.click(screen.getByRole("button", { name: "Send" }));
    const field = screen.getByRole("textbox", { name: /Email/ });
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAccessibleDescription(/Enter an email address\./);
  });
});
