import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Search } from "./Search";

describe("Search", () => {
  it("is a labelled search input and passes axe", async () => {
    const { container } = render(
      <Search label="Search records" isLabelHidden />,
    );
    const input = screen.getByRole("searchbox", { name: "Search records" });
    expect(input).toHaveAttribute("type", "search");
    await expectNoA11yViolations(container);
  });

  it("works uncontrolled and clears with the clear button", async () => {
    const user = userEvent.setup();
    const onClear = vi.fn();
    render(<Search label="Search" onClear={onClear} />);
    const input = screen.getByRole("searchbox");
    await user.type(input, "chennai");
    await user.click(screen.getByRole("button", { name: "Clear search" }));
    expect(input).toHaveValue("");
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it("clears with Escape and submits with Enter", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Search label="Search" onSubmit={onSubmit} />);
    const input = screen.getByRole("searchbox");
    await user.type(input, "kochi{Enter}");
    expect(onSubmit).toHaveBeenCalledWith("kochi");
    await user.keyboard("{Escape}");
    expect(input).toHaveValue("");
  });

  it("works controlled and never searches by itself", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    function Controlled() {
      const [value, setValue] = useState("");
      return (
        <Search
          label="Search"
          value={value}
          onChange={(next) => {
            onChange(next);
            setValue(next);
          }}
        />
      );
    }
    render(<Controlled />);
    await user.type(screen.getByRole("searchbox"), "ab");
    expect(onChange).toHaveBeenLastCalledWith("ab");
  });

  it("announces a loading state and renders a suggestions slot", () => {
    render(
      <Search
        label="Search"
        isLoading
        loadingLabel="Searching records…"
        suggestions={<p>Recent: Mumbai campus</p>}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Searching records…");
    expect(screen.getByText("Recent: Mumbai campus")).toBeInTheDocument();
  });
});

describe("Search announcements (T00-10)", () => {
  it("keeps its status region mounted so the loading text is announced", () => {
    const { rerender } = render(
      <Search label="Search records" loadingLabel="Searching records…" />,
    );
    const status = screen.getByRole("status");
    expect(status).toBeEmptyDOMElement();
    rerender(
      <Search
        label="Search records"
        isLoading
        loadingLabel="Searching records…"
      />,
    );
    expect(screen.getByRole("status")).toBe(status);
    expect(status).toHaveTextContent("Searching records…");
  });
});
