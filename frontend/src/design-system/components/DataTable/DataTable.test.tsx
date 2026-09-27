import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useMemo, useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Badge } from "@/design-system/components/Badge";
import { IconButton } from "@/design-system/components/IconButton";
import { Pagination } from "@/design-system/components/Pagination";
import { ViewIcon } from "@/design-system/icons";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import {
  DataTable,
  type DataTableColumn,
  type DataTableProps,
  type SortDescriptor,
} from "./DataTable";

type Vessel = {
  id: string;
  name: string;
  type: string;
  tonnage: number;
  status: "Active" | "Laid up";
};

const ROWS: Vessel[] = [
  {
    id: "v1",
    name: "MV Sagar Kanya",
    type: "Research",
    tonnage: 4200,
    status: "Active",
  },
  {
    id: "v2",
    name: "MT Desh Shakti",
    type: "Tanker",
    tonnage: 158000,
    status: "Active",
  },
  {
    id: "v3",
    name: "MV Coral Star",
    type: "Bulk carrier",
    tonnage: 76000,
    status: "Laid up",
  },
];

const COLUMNS: DataTableColumn<Vessel>[] = [
  {
    id: "name",
    header: "Vessel",
    cell: (row) => row.name,
    isSortable: true,
    isRowHeader: true,
  },
  {
    id: "type",
    header: "Type",
    cell: (row) => row.type,
    visibleFrom: "tablet",
  },
  {
    id: "tonnage",
    header: "Tonnage",
    cell: (row) => row.tonnage.toLocaleString("en-IN"),
    isSortable: true,
    align: "end",
  },
  {
    id: "status",
    header: "Status",
    cell: (row) => (
      <Badge tone={row.status === "Active" ? "success" : "neutral"}>
        {row.status}
      </Badge>
    ),
  },
];

function Table(props: Partial<DataTableProps<Vessel>>) {
  return (
    <DataTable
      label="Vessels"
      columns={COLUMNS}
      rows={ROWS}
      getRowId={(row) => row.id}
      getRowLabel={(row) => row.name}
      {...props}
    />
  );
}

function Sortable() {
  const [sort, setSort] = useState<SortDescriptor | null>(null);
  const rows = useMemo(() => {
    if (!sort) return ROWS;
    const key = sort.columnId as "name" | "tonnage";
    const sorted = [...ROWS].sort((a, b) =>
      a[key] < b[key] ? -1 : a[key] > b[key] ? 1 : 0,
    );
    return sort.direction === "ascending" ? sorted : sorted.reverse();
  }, [sort]);
  return <Table rows={rows} sort={sort} onSortChange={setSort} />;
}

const bodyRowNames = () =>
  within(screen.getByRole("table"))
    .getAllByRole("rowheader")
    .map((cell) => cell.textContent);

describe("DataTable", () => {
  it("renders a captioned table with row headers and passes axe", async () => {
    const { container } = render(<Table />);
    const table = screen.getByRole("table", { name: "Vessels" });
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual(["Vessel", "Type", "Tonnage", "Status"]);
    expect(bodyRowNames()).toEqual([
      "MV Sagar Kanya",
      "MT Desh Shakti",
      "MV Coral Star",
    ]);
    await expectNoA11yViolations(container);
  });

  it("cycles sorting ascending → descending → unsorted with aria-sort", async () => {
    const user = userEvent.setup();
    render(<Sortable />);
    const header = () => screen.getByRole("columnheader", { name: "Tonnage" });
    const button = screen.getByRole("button", { name: "Tonnage" });

    expect(header()).toHaveAttribute("aria-sort", "none");
    await user.click(button);
    expect(header()).toHaveAttribute("aria-sort", "ascending");
    expect(bodyRowNames()[0]).toBe("MV Sagar Kanya");
    await user.click(button);
    expect(header()).toHaveAttribute("aria-sort", "descending");
    expect(bodyRowNames()[0]).toBe("MT Desh Shakti");
    await user.click(button);
    expect(header()).toHaveAttribute("aria-sort", "none");
  });

  it("sorts from the keyboard", async () => {
    const user = userEvent.setup();
    render(<Sortable />);
    screen.getByRole("button", { name: "Vessel" }).focus();
    await user.keyboard("{Enter}");
    expect(
      screen.getByRole("columnheader", { name: "Vessel" }),
    ).toHaveAttribute("aria-sort", "ascending");
  });

  it("selects rows, selects all and shows the indeterminate state", async () => {
    const user = userEvent.setup();
    const onSelectionChange = vi.fn();
    function Selectable() {
      const [selected, setSelected] = useState<Set<string>>(new Set());
      return (
        <Table
          selectionMode="multiple"
          selectedIds={selected}
          onSelectionChange={(ids) => {
            onSelectionChange(ids);
            setSelected(ids);
          }}
        />
      );
    }
    render(<Selectable />);
    const selectAll = () =>
      screen.getByRole<HTMLInputElement>("checkbox", {
        name: "Select all rows",
      });

    await user.click(
      screen.getByRole("checkbox", { name: "Select MT Desh Shakti" }),
    );
    expect(selectAll().indeterminate).toBe(true);
    expect(onSelectionChange).toHaveBeenLastCalledWith(new Set(["v2"]));

    await user.click(selectAll());
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      new Set(["v1", "v2", "v3"]),
    );
    expect(selectAll().checked).toBe(true);

    await user.click(selectAll());
    expect(onSelectionChange).toHaveBeenLastCalledWith(new Set());
  });

  it("keeps at most one row selected in single mode", async () => {
    const user = userEvent.setup();
    function Single() {
      const [selected, setSelected] = useState<Set<string>>(new Set(["v1"]));
      return (
        <Table
          selectionMode="single"
          selectedIds={selected}
          onSelectionChange={setSelected}
        />
      );
    }
    render(<Single />);
    expect(
      screen.queryByRole("checkbox", { name: "Select all rows" }),
    ).toBeNull();
    await user.click(
      screen.getByRole("checkbox", { name: "Select MV Coral Star" }),
    );
    expect(
      screen.getByRole("checkbox", { name: "Select MV Coral Star" }),
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Select MV Sagar Kanya" }),
    ).not.toBeChecked();
  });

  it("renders business-neutral row actions", async () => {
    const user = userEvent.setup();
    const onView = vi.fn<(id: string) => void>();
    render(
      <Table
        rowActions={(row) => (
          <IconButton
            label={`View ${row.name}`}
            icon={ViewIcon}
            onPress={() => onView(row.id)}
          />
        )}
      />,
    );
    expect(
      screen.getByRole("columnheader", { name: "Actions" }),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "View MV Coral Star" }),
    );
    expect(onView).toHaveBeenCalledWith("v3");
  });

  it("shows an accessible loading state with skeleton rows", async () => {
    const { container } = render(
      <Table isLoading loadingLabel="Loading vessels" loadingRows={4} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading vessels");
    expect(screen.getByRole("table")).toHaveAttribute("aria-busy", "true");
    expect(
      container.querySelectorAll("tbody tr[aria-hidden='true']"),
    ).toHaveLength(4);
    await expectNoA11yViolations(container);
  });

  it("shows the caller's empty state", async () => {
    const { container } = render(
      <Table
        rows={[]}
        emptyState={{
          title: "No vessels yet",
          description: "Add a vessel to get started.",
        }}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "No vessels yet" }),
    ).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("shows an error state with retry", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<Table error={{ title: "We couldn't load vessels", onRetry }} />);
    expect(
      screen.getByRole("heading", { name: "We couldn't load vessels" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("scrolls inside a focusable region and hides low-priority columns on mobile", () => {
    render(<Table />);
    const region = screen.getByRole("region", { name: "Vessels" });
    expect(region).toHaveAttribute("tabindex", "0");
    expect(region.className).toContain("overflow-x-auto");
    expect(
      screen.getByRole("columnheader", { name: "Type" }).className,
    ).toContain("hidden tablet:table-cell");
  });

  it("renders cards on mobile when requested", async () => {
    const { container } = render(<Table mobileLayout="cards" />);
    const list = screen.getByRole("list", { name: "Vessels" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    expect(within(list).getAllByText("Tonnage")).toHaveLength(3);
    await expectNoA11yViolations(container);
  });

  it("integrates Pagination through the footer slot", () => {
    render(
      <Table
        footer={
          <Pagination
            page={1}
            pageSize={25}
            totalItems={3}
            onPageChange={() => {}}
          />
        }
      />,
    );
    expect(
      screen.getByRole("navigation", { name: "Pagination" }),
    ).toBeInTheDocument();
  });
});
