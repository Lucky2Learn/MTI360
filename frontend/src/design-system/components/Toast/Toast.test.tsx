import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";

import {
  createToastQueue,
  showToast,
  toast,
  toastQueue,
  ToastRegion,
  type ToastQueue,
} from "./Toast";

// A focusable element outside the region: React Aria's toast region restores
// focus to the focus event's relatedTarget. In jsdom + user-event that can be
// the document object (no .focus()) when nothing was focused; in browsers it
// is an element or null. Focusing a real element first mirrors browser use.
function setup(queue: ToastQueue = createToastQueue()) {
  render(
    <>
      <button type="button">Page content</button>
      <ToastRegion queue={queue} />
    </>,
  );
  screen.getByRole("button", { name: "Page content" }).focus();
  return queue;
}

afterEach(() => {
  vi.useRealTimers();
  act(() => toastQueue.clear());
});

describe("Toast", () => {
  it("announces a toast in a labelled notifications region and passes axe", async () => {
    const queue = setup();
    act(() => {
      showToast(
        {
          tone: "success",
          title: "Record saved",
          description: "All changes were saved.",
        },
        {},
        queue,
      );
    });
    const region = screen.getByRole("region", { name: "Notifications" });
    const alert = within(region).getByRole("alertdialog");
    expect(alert).toHaveTextContent("Record saved");
    expect(alert).toHaveTextContent("All changes were saved.");
    await expectNoA11yViolations(document.body);
  });

  it("dismisses with the close button", async () => {
    const user = userEvent.setup();
    const queue = setup();
    act(() => {
      showToast({ tone: "info", title: "Export ready" }, {}, queue);
    });
    await user.click(
      screen.getByRole("button", { name: "Dismiss notification" }),
    );
    await waitFor(() => expect(screen.queryByText("Export ready")).toBeNull());
  });

  it("runs an action and closes", async () => {
    const user = userEvent.setup();
    const onAction = vi.fn();
    const queue = setup();
    act(() => {
      showToast(
        {
          tone: "info",
          title: "Record archived",
          action: { label: "Undo", onAction },
        },
        {},
        queue,
      );
    });
    await user.click(screen.getByRole("button", { name: "Undo" }));
    expect(onAction).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(screen.queryByText("Record archived")).toBeNull(),
    );
  });

  it("auto-dismisses success after 5 s but keeps errors and action toasts", () => {
    vi.useFakeTimers();
    const queue = setup();
    act(() => {
      showToast({ tone: "success", title: "Saved" }, {}, queue);
      showToast({ tone: "error", title: "Upload failed" }, {}, queue);
      showToast(
        {
          tone: "info",
          title: "Moved",
          action: { label: "Undo", onAction: () => {} },
        },
        {},
        queue,
      );
    });
    act(() => {
      vi.advanceTimersByTime(4900);
    });
    expect(screen.getByText("Saved")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(screen.queryByText("Saved")).toBeNull();
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByText("Upload failed")).toBeInTheDocument();
    expect(screen.getByText("Moved")).toBeInTheDocument();
  });

  it("honours a custom duration", () => {
    vi.useFakeTimers();
    const queue = setup();
    act(() => {
      showToast(
        { tone: "warning", title: "Session expiring" },
        { timeout: 10_000 },
        queue,
      );
    });
    act(() => {
      vi.advanceTimersByTime(9_000);
    });
    expect(screen.getByText("Session expiring")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(1_100);
    });
    expect(screen.queryByText("Session expiring")).toBeNull();
  });

  it("stacks multiple toasts and shows at most three at once", () => {
    const queue = setup();
    act(() => {
      for (const title of ["One", "Two", "Three", "Four"]) {
        showToast({ tone: "error", title }, {}, queue);
      }
    });
    const region = screen.getByRole("region", { name: "Notifications" });
    expect(within(region).getAllByRole("alertdialog")).toHaveLength(3);
  });

  it("offers shorthands on the default queue", () => {
    render(<ToastRegion />);
    act(() => {
      toast.warning("Medical certificate expires soon", {
        description: "3 cadets affected.",
      });
    });
    expect(
      screen.getByText("Medical certificate expires soon"),
    ).toBeInTheDocument();
    expect(screen.getByText("3 cadets affected.")).toBeInTheDocument();
  });
});
