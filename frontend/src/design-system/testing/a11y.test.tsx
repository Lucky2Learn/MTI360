import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Button, Dialog, IconButton, Input } from "@/design-system/components";
import { CloseIcon } from "@/design-system/icons";

import {
  expectFocusContained,
  expectHeadingOutline,
  expectFocusRing,
  expectNamedControls,
  tabSequence,
} from "./a11y";

describe("expectNamedControls", () => {
  it("passes when every control has an accessible name", () => {
    const { container } = render(
      <div>
        <Button>Save batch</Button>
        <IconButton label="Close" icon={CloseIcon} />
        <Input label="Batch code" />
        <a href="#dashboard">Dashboard</a>
      </div>,
    );
    expectNamedControls(container);
  });

  it("fails for an unnamed icon-only button", () => {
    const { container } = render(
      <div>
        <button type="button">
          <svg aria-hidden="true" />
        </button>
      </div>,
    );
    expect(() => expectNamedControls(container)).toThrow();
  });
});

describe("tabSequence", () => {
  it("returns the focus order", async () => {
    const user = userEvent.setup();
    render(
      <>
        <Button>First</Button>
        <IconButton label="Second" icon={CloseIcon} />
        <a href="#third">Third</a>
      </>,
    );
    expect(await tabSequence(user, 3)).toEqual(["First", "Second", "Third"]);
    expect(await tabSequence(user, 2, { shift: true })).toEqual([
      "Second",
      "First",
    ]);
  });
});

describe("expectFocusContained", () => {
  it("passes for a modal dialog", async () => {
    const user = userEvent.setup();
    render(
      <>
        <Button>Outside</Button>
        <Dialog
          title="Edit vessel"
          trigger={<Button>Open</Button>}
          actions={(close) => <Button onPress={close}>Done</Button>}
        >
          <Input label="Call sign" />
        </Dialog>
      </>,
    );
    await user.click(screen.getByRole("button", { name: "Open" }));
    const dialog = await screen.findByRole("dialog");
    await expectFocusContained(user, dialog);
    expect(
      within(dialog).getByRole("textbox", { name: "Call sign" }),
    ).toBeInTheDocument();
  });

  it("fails when focus can leave", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <>
        <div data-testid="group">
          <Button>Inside</Button>
        </div>
        <Button>Outside</Button>
      </>,
    );
    screen.getByRole("button", { name: "Inside" }).focus();
    await expect(
      expectFocusContained(user, within(container).getByTestId("group"), 2),
    ).rejects.toThrow();
  });
});

describe("expectFocusRing", () => {
  it("accepts the shared ring on the element or its field wrapper", () => {
    render(
      <>
        <Button>Save</Button>
        <Input label="Batch code" />
      </>,
    );
    expectFocusRing(screen.getByRole("button", { name: "Save" }));
    expectFocusRing(screen.getByRole("textbox", { name: "Batch code" }));
  });

  it("rejects an element without the token ring", () => {
    render(
      <button type="button" className="outline-none">
        Bare
      </button>,
    );
    expect(() =>
      expectFocusRing(screen.getByRole("button", { name: "Bare" })),
    ).toThrow(/no token focus ring/);
  });
});

describe("expectHeadingOutline", () => {
  it("accepts one h1 followed by nested levels without gaps", () => {
    const { container } = render(
      <main>
        <h1>Batches</h1>
        <h2>Upcoming</h2>
        <h3>DNS 2026-B</h3>
        <h2>Archived</h2>
      </main>,
    );
    expect(expectHeadingOutline(container)).toEqual([1, 2, 3, 2]);
  });

  it("rejects a missing or repeated h1 and skipped levels", () => {
    const skipped = render(
      <main>
        <h1>Batches</h1>
        <h3>Upcoming</h3>
      </main>,
    );
    expect(() => expectHeadingOutline(skipped.container)).toThrow();
    skipped.unmount();
    const twoH1 = render(
      <main>
        <h1>Batches</h1>
        <h1>Courses</h1>
      </main>,
    );
    expect(() => expectHeadingOutline(twoH1.container)).toThrow();
  });
});
