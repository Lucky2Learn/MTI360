import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import type { ActivityWire } from "@/lib/api/admissions";
import { renderScreen } from "@/test/render-screen";

import { ActivityFeed } from "../activity/ActivityFeed";

import {
  StatusTransitionDialog,
  type TransitionOutcome,
} from "./StatusTransitionDialog";

vi.setConfig({ testTimeout: 30_000 });

// Shared business components (Phase 02-1; blueprint §28): the status dialog
// offers only the server's choices, requires a reason when the choice does,
// and closes only when the server accepted; the activity feed renders notes
// as plain text.

const CHOICES = [
  {
    value: "CONTACTED",
    label: "Contacted",
    requiresReason: false,
    requiresTarget: false,
  },
  { value: "LOST", label: "Lost", requiresReason: true, requiresTarget: false },
];

function renderDialog(
  onSubmit: (input: unknown) => Promise<TransitionOutcome>,
  onOpenChange = vi.fn(),
) {
  return renderScreen(
    <StatusTransitionDialog
      isOpen
      onOpenChange={onOpenChange}
      title="Move Arjun Nair to…"
      description="Current status: New"
      choices={CHOICES}
      onSubmit={onSubmit}
    />,
  );
}

async function choose(user: ReturnType<typeof userEvent.setup>, label: string) {
  await user.click(screen.getByRole("button", { name: /New status/ }));
  await user.click(await screen.findByRole("option", { name: label }));
}

describe("StatusTransitionDialog", () => {
  it("offers only the given choices and requires a reason for closing ones", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn(() => Promise.resolve({ kind: "done" } as const));
    renderDialog(onSubmit);
    await user.click(screen.getByRole("button", { name: /New status/ }));
    expect(
      (await screen.findAllByRole("option")).map((o) => o.textContent),
    ).toEqual(["Contacted", "Lost"]);
    await user.click(screen.getByRole("option", { name: "Lost" }));
    await user.click(screen.getByRole("button", { name: "Save status" }));
    expect(await screen.findByText("Enter a reason.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: /Reason/ })).toHaveFocus(),
    );
    await user.type(
      screen.getByRole("textbox", { name: /Reason/ }),
      "Joined elsewhere",
    );
    await user.click(screen.getByRole("button", { name: "Save status" }));
    expect(onSubmit).toHaveBeenCalledWith({
      to: "LOST",
      reason: "Joined elsewhere",
      targetId: null,
    });
  });

  it("stays open with the server's answer until it accepts (no optimistic close)", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onSubmit = vi.fn(() =>
      Promise.resolve({
        kind: "feedback",
        feedback: {
          tone: "warning",
          title: "This was changed by someone else",
        },
      } as const),
    );
    renderDialog(onSubmit, onOpenChange);
    await choose(user, "Contacted");
    await user.click(screen.getByRole("button", { name: "Save status" }));
    expect(
      await screen.findByText("This was changed by someone else"),
    ).toBeInTheDocument();
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
    await expectNoA11yViolations(screen.getByRole("dialog"));
  });
});

describe("ActivityFeed", () => {
  it("renders notes as plain text, never as HTML", () => {
    const activities: ActivityWire[] = [
      {
        id: "a1",
        kind: "NOTE",
        actor: { display_name: "Ravi Menon" },
        details: {},
        body: "<img src=x onerror=alert(1)> Call after 6 pm",
        created_at: "2026-10-08T10:00:00Z",
      },
    ];
    const { container } = renderScreen(
      <ActivityFeed
        activities={activities}
        describe={() => ({ title: "Note" })}
        label="Lead history"
      />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(
      screen.getByText("<img src=x onerror=alert(1)> Call after 6 pm"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("list", { name: "Lead history" }),
    ).toBeInTheDocument();
  });
});
