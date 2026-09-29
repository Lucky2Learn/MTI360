import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Pagination, pageItems } from "./Pagination";

function Controlled({ total = 1284, onPageChange = vi.fn() }) {
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(25);
  return (
    <Pagination
      page={page}
      pageSize={size}
      totalItems={total}
      pageSizeOptions={[10, 25, 50]}
      onPageSizeChange={(next) => {
        setSize(next);
        setPage(1);
      }}
      onPageChange={(next) => {
        onPageChange(next);
        setPage(next);
      }}
      itemLabel="records"
    />
  );
}

const full = () => screen.getAllByRole("list")[0]!;

describe("pageItems", () => {
  it.each([
    [1, 5, [1, 2, 3, 4, 5]],
    [1, 52, [1, 2, 3, 4, 5, "ellipsis-end", 52]],
    [26, 52, [1, "ellipsis-start", 25, 26, 27, "ellipsis-end", 52]],
    [52, 52, [1, "ellipsis-start", 48, 49, 50, 51, 52]],
  ])("page %i of %i", (page, total, expected) => {
    expect(pageItems(page, total)).toEqual(expected);
  });
});

describe("Pagination", () => {
  it("is a labelled navigation landmark with a summary and passes axe", async () => {
    const { container } = render(<Controlled />);
    expect(
      screen.getByRole("navigation", { name: "Pagination" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Showing 1–25 of 1,284 records"),
    ).toBeInTheDocument();
    expect(
      within(full()).getByRole("button", { name: "Page 1" }),
    ).toHaveAttribute("aria-current", "page");
    await expectNoA11yViolations(container);
  });

  it("disables First/Previous on the first page and Next/Last on the last", async () => {
    const user = userEvent.setup();
    render(<Controlled total={60} />);
    expect(
      within(full()).getByRole("button", { name: "First page" }),
    ).toBeDisabled();
    expect(
      within(full()).getByRole("button", { name: "Previous page" }),
    ).toBeDisabled();
    await user.click(within(full()).getByRole("button", { name: "Last page" }));
    expect(
      within(full()).getByRole("button", { name: "Next page" }),
    ).toBeDisabled();
    expect(
      within(full()).getByRole("button", { name: "Page 3" }),
    ).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("Showing 51–60 of 60 records")).toBeInTheDocument();
  });

  it("navigates with Next, Previous and page numbers via the keyboard", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(<Controlled onPageChange={onPageChange} />);
    within(full()).getByRole("button", { name: "Next page" }).focus();
    await user.keyboard("{Enter}");
    expect(onPageChange).toHaveBeenLastCalledWith(2);
    await user.click(within(full()).getByRole("button", { name: "Page 3" }));
    expect(onPageChange).toHaveBeenLastCalledWith(3);
    await user.click(
      within(full()).getByRole("button", { name: "Previous page" }),
    );
    expect(onPageChange).toHaveBeenLastCalledWith(2);
  });

  it("changes the page size", async () => {
    const user = userEvent.setup();
    render(<Controlled />);
    await user.click(screen.getByRole("button", { name: /Rows per page/ }));
    await user.click(screen.getByRole("option", { name: "50" }));
    expect(
      screen.getByText("Showing 1–50 of 1,284 records"),
    ).toBeInTheDocument();
  });

  it("has a compact mobile layout", () => {
    render(<Controlled />);
    expect(screen.getByText("Page 1 of 52")).toBeInTheDocument();
  });

  it("handles zero items", () => {
    render(
      <Pagination
        page={1}
        pageSize={25}
        totalItems={0}
        onPageChange={() => {}}
      />,
    );
    expect(screen.getByText("No items")).toBeInTheDocument();
  });
});

describe("Pagination focus (T00-10)", () => {
  it("moves focus to the current page when the pressed control becomes disabled", async () => {
    const user = userEvent.setup();
    render(<Controlled />);
    const last = within(full()).getByRole("button", { name: "Last page" });
    last.focus();
    await user.keyboard("{Enter}");
    expect(last).toBeDisabled();
    const current = within(full()).getByRole("button", { name: "Page 52" });
    expect(current).toHaveAttribute("aria-current", "page");
    expect(current).toHaveFocus();

    within(full()).getByRole("button", { name: "First page" }).focus();
    await user.keyboard("{Enter}");
    expect(
      within(full()).getByRole("button", { name: "Page 1" }),
    ).toHaveFocus();
  });

  it("keeps focus on the pressed control while it stays enabled", async () => {
    const user = userEvent.setup();
    render(<Controlled />);
    const next = within(full()).getByRole("button", { name: "Next page" });
    next.focus();
    await user.keyboard("{Enter}");
    await user.keyboard("{Enter}");
    expect(next).toHaveFocus();
    expect(
      within(full()).getByRole("button", { name: "Page 3" }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("does not move focus when the page changes from outside", () => {
    const { rerender } = render(
      <>
        <button type="button">Elsewhere</button>
        <Pagination
          page={1}
          pageSize={25}
          totalItems={100}
          onPageChange={vi.fn()}
        />
      </>,
    );
    const elsewhere = screen.getByRole("button", { name: "Elsewhere" });
    elsewhere.focus();
    rerender(
      <>
        <button type="button">Elsewhere</button>
        <Pagination
          page={4}
          pageSize={25}
          totalItems={100}
          onPageChange={vi.fn()}
        />
      </>,
    );
    expect(elsewhere).toHaveFocus();
  });
});
