import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "@/design-system/components/Button";

import { NavigationProvider } from "./NavigationProvider";

describe("NavigationProvider", () => {
  it("routes React Aria links through the supplied navigate function", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn();
    render(
      <NavigationProvider navigate={navigate}>
        <Button href="/app/finance">Finance</Button>
      </NavigationProvider>,
    );
    const link = screen.getByRole("link", { name: "Finance" });
    expect(link).toHaveAttribute("href", "/app/finance");
    await user.click(link);
    expect(navigate).toHaveBeenCalledWith("/app/finance", undefined);
  });
});
