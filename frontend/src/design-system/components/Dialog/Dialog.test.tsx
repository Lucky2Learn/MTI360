import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "@/design-system/components/Button";
import { Input } from "@/design-system/components/Input";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { AlertDialog } from "./AlertDialog";
import { Dialog } from "./Dialog";

function EditDialog(props: { isDismissable?: boolean; onSave?: () => void }) {
  return (
    <Dialog
      title="Edit batch"
      description="Changes apply to all cadets in the batch."
      trigger={<Button>Edit batch</Button>}
      isDismissable={props.isDismissable}
      actions={(close) => (
        <>
          <Button variant="secondary" onPress={close}>
            Cancel
          </Button>
          <Button
            onPress={() => {
              props.onSave?.();
              close();
            }}
          >
            Save
          </Button>
        </>
      )}
    >
      <Input label="Batch name" defaultValue="DNS 2026-B" />
    </Dialog>
  );
}

describe("Dialog", () => {
  it("opens from its trigger as a labelled, described dialog and passes axe", async () => {
    const user = userEvent.setup();
    render(<EditDialog />);
    await user.click(screen.getByRole("button", { name: "Edit batch" }));

    const dialog = screen.getByRole("dialog", { name: "Edit batch" });
    expect(dialog).toHaveAccessibleDescription(
      "Changes apply to all cadets in the batch.",
    );
    await expectNoA11yViolations(document.body);
  });

  it("moves focus inside, traps Tab and restores focus to the trigger on Escape", async () => {
    const user = userEvent.setup();
    render(<EditDialog />);
    const trigger = screen.getByRole("button", { name: "Edit batch" });
    await user.click(trigger);

    const dialog = screen.getByRole("dialog");
    await waitFor(() =>
      expect(dialog.contains(document.activeElement)).toBe(true),
    );
    for (let i = 0; i < 6; i += 1) {
      await user.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("closes with the close button and with actions that receive close()", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<EditDialog onSave={onSave} />);

    await user.click(screen.getByRole("button", { name: "Edit batch" }));
    await user.click(screen.getByRole("button", { name: "Close dialog" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    await user.click(screen.getByRole("button", { name: "Edit batch" }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("closes on outside interaction when dismissable, not otherwise", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<EditDialog />);
    await user.click(screen.getByRole("button", { name: "Edit batch" }));
    await user.click(document.body);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    unmount();

    render(<EditDialog isDismissable={false} />);
    await user.click(screen.getByRole("button", { name: "Edit batch" }));
    await user.click(document.body);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("supports controlled use without a trigger and size variants", async () => {
    const user = userEvent.setup();
    function Controlled() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <Button onPress={() => setOpen(true)}>Open details</Button>
          <output>{open ? "open" : "closed"}</output>
          <Dialog
            title="Batch details"
            size="xl"
            isOpen={open}
            onOpenChange={setOpen}
          >
            Details
          </Dialog>
        </>
      );
    }
    render(<Controlled />);
    await user.click(screen.getByRole("button", { name: "Open details" }));
    const dialog = screen.getByRole("dialog", { name: "Batch details" });
    expect(dialog.parentElement?.className).toContain("tablet:max-w-4xl");
    await user.keyboard("{Escape}");
    expect(screen.getByText("closed")).toBeInTheDocument();
  });
});

describe("AlertDialog", () => {
  function DeleteConfirm(props: {
    onConfirm: () => void;
    onCancel?: () => void;
  }) {
    return (
      <AlertDialog
        trigger={<Button variant="destructive">Delete record</Button>}
        title="Delete this record?"
        description="This permanently removes the record and cannot be undone."
        confirmLabel="Delete record"
        tone="destructive"
        onConfirm={props.onConfirm}
        onCancel={props.onCancel}
      />
    );
  }

  it("uses alertdialog semantics, focuses the safest action and passes axe", async () => {
    const user = userEvent.setup();
    render(<DeleteConfirm onConfirm={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Delete record" }));

    const dialog = screen.getByRole("alertdialog", {
      name: "Delete this record?",
    });
    expect(dialog).toHaveAccessibleDescription(
      "This permanently removes the record and cannot be undone.",
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus(),
    );
    await expectNoA11yViolations(document.body);
  });

  it("confirms with an explicit, destructive-styled action", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<DeleteConfirm onConfirm={onConfirm} />);
    await user.click(screen.getByRole("button", { name: "Delete record" }));
    const confirm = screen
      .getAllByRole("button", { name: "Delete record" })
      .find((button) => screen.getByRole("alertdialog").contains(button))!;
    expect(confirm.className).toContain("bg-error-strong");
    await user.click(confirm);
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  });

  it("cancels with Escape and the Cancel button, never on outside click", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<DeleteConfirm onConfirm={onConfirm} onCancel={onCancel} />);

    await user.click(screen.getByRole("button", { name: "Delete record" }));
    await user.click(document.body);
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());

    await user.click(screen.getByRole("button", { name: "Delete record" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
