import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Search } from "@/design-system/components/Search";
import { Select } from "@/design-system/components/Select";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { FilterBar } from "./FilterBar";

const STATUS = [
  { id: "active", label: "Active" },
  { id: "archived", label: "Archived" },
];

function Bar(props: {
  onClear?: () => void;
  onApply?: () => void;
  count?: number;
}) {
  return (
    <FilterBar
      search={<Search label="Search records" isLabelHidden />}
      filters={<Select label="Status" options={STATUS} />}
      activeFilterCount={props.count ?? 1}
      resultCount="128 results"
      onClear={props.onClear}
      onApply={props.onApply}
    />
  );
}

describe("FilterBar", () => {
  it("renders search, a labelled filter group and the result count; passes axe", async () => {
    const { container } = render(<Bar onClear={vi.fn()} />);
    expect(
      screen.getByRole("searchbox", { name: "Search records" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Filters" })).toBeInTheDocument();
    expect(screen.getByText("128 results")).toHaveAttribute(
      "aria-live",
      "polite",
    );
    await expectNoA11yViolations(container);
  });

  it("clears and applies inline (tablet and up)", async () => {
    const user = userEvent.setup();
    const onClear = vi.fn();
    const onApply = vi.fn();
    render(<Bar onClear={onClear} onApply={onApply} />);
    const group = screen.getByRole("group", { name: "Filters" });
    await user.click(
      within(group).getByRole("button", { name: "Clear filters" }),
    );
    await user.click(within(group).getByRole("button", { name: "Apply" }));
    expect(onClear).toHaveBeenCalledTimes(1);
    expect(onApply).toHaveBeenCalledTimes(1);
  });

  it("opens the filters in a Drawer on mobile, applies and closes", async () => {
    const user = userEvent.setup();
    const onApply = vi.fn();
    render(<Bar count={2} onClear={vi.fn()} onApply={onApply} />);
    await user.click(screen.getByRole("button", { name: "Filters (2)" }));

    const drawer = screen.getByRole("dialog", { name: "Filters" });
    expect(drawer).toBeInTheDocument();
    await expectNoA11yViolations(document.body);

    const applyButtons = screen.getAllByRole("button", { name: "Apply" });
    await user.click(applyButtons.find((button) => drawer.contains(button))!);
    expect(onApply).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("uses Done when filters apply immediately", async () => {
    const user = userEvent.setup();
    render(<Bar count={0} />);
    await user.click(screen.getByRole("button", { name: "Filters" }));
    await user.click(screen.getByRole("button", { name: "Done" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
