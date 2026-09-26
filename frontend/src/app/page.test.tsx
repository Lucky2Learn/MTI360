import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "./page";

// Toolchain smoke test (T00-02): proves the Vitest + jsdom + Testing Library
// setup renders a React component. Not a product/business test.
describe("HomePage", () => {
  it("renders the MTI 360 level-one heading", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "MTI 360" }),
    ).toBeInTheDocument();
  });
});
