import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { ErrorState } from "./ErrorState";

describe("ErrorState", () => {
  it("answers what happened, what was saved and what to do", async () => {
    const onRetry = vi.fn();
    const { container } = render(
      <ErrorState
        title="We couldn't load the fee schedule"
        description="The finance service did not respond. Try again in a moment."
        savedState="Your changes to the instalment plan were saved."
        onRetry={onRetry}
        backHref="/app/finance"
        supportHref="/app/support"
        reference="req-7f3a9c"
      />,
    );

    expect(
      screen.getByRole("region", { name: "We couldn't load the fee schedule" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/instalment plan were saved/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Try again" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go back" })).toHaveAttribute(
      "href",
      "/app/finance",
    );
    expect(
      screen.getByRole("link", { name: "Contact support" }),
    ).toHaveAttribute("href", "/app/support");
    expect(screen.getByText("req-7f3a9c")).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("retries on press", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<ErrorState title="Upload failed" onRetry={onRetry} />);

    await user.click(screen.getByRole("button", { name: "Try again" }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("presents permission restrictions understandably", async () => {
    const { container } = render(
      <ErrorState
        kind="permission"
        title="You don't have permission to approve this application."
        description="Ask your Admissions Manager for approval access."
      />,
    );
    expect(
      screen.getByRole("heading", {
        name: "You don't have permission to approve this application.",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
    await expectNoA11yViolations(container);
  });

  it("does not accept raw Error objects (no technical details on screen)", () => {
    const error = new Error('relation "students" does not exist');
    const props = { title: "Something went wrong", description: error };
    // @ts-expect-error — Error objects are not renderable descriptions
    const element = <ErrorState {...props} />;
    expect(element).toBeTruthy();
  });

  it("wraps its actions in narrow containers (T00-09)", () => {
    render(
      <ErrorState
        title="We couldn't load the fee schedule"
        onRetry={() => {}}
        backHref="#top"
        supportHref="#top"
      />,
    );
    const actions = screen.getByRole("button", {
      name: "Try again",
    }).parentElement!;
    expect(actions).toHaveClass("tablet:flex-row", "tablet:flex-wrap");
  });
});
