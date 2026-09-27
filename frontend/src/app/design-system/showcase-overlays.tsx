"use client";

import { useMemo, useState, type ReactNode } from "react";

import {
  AlertDialog,
  Badge,
  Button,
  ContextMenu,
  createToastQueue,
  DataTable,
  DatePicker,
  Dialog,
  Drawer,
  DropdownMenu,
  FilterBar,
  IconButton,
  Input,
  Pagination,
  Popover,
  RadioGroup,
  Search,
  Select,
  showToast,
  Switch,
  TimePicker,
  ToastRegion,
  Tooltip,
  type DataTableColumn,
  type MenuEntry,
  type SortDescriptor,
} from "@/design-system/components";
import {
  CopyIcon,
  DeleteIcon,
  DownloadIcon,
  EditIcon,
  MenuIcon,
  MoreIcon,
  SettingsIcon,
  ViewIcon,
} from "@/design-system/icons";

// T00-07C showcase: overlays, data and interaction controls (development/test
// only; see gate.ts). Generic sample data; nothing is fetched or submitted.
// The showcase mounts its own ToastRegion (the application shell mounts the
// global one in T00-08).

const showcaseToasts = createToastQueue();

type Vessel = {
  id: string;
  name: string;
  type: string;
  port: string;
  tonnage: number;
  status: "Active" | "In dry dock" | "Laid up";
};

const VESSELS: Vessel[] = [
  {
    id: "v01",
    name: "MV Coral Star",
    type: "Bulk carrier",
    port: "Mumbai",
    tonnage: 76000,
    status: "Active",
  },
  {
    id: "v02",
    name: "MT Desh Shakti",
    type: "Tanker",
    port: "Chennai",
    tonnage: 158000,
    status: "Active",
  },
  {
    id: "v03",
    name: "MV Sagar Kanya",
    type: "Research",
    port: "Kochi",
    tonnage: 4200,
    status: "In dry dock",
  },
  {
    id: "v04",
    name: "MV Blue Horizon",
    type: "Container",
    port: "Visakhapatnam",
    tonnage: 52000,
    status: "Active",
  },
  {
    id: "v05",
    name: "MT Ocean Pearl",
    type: "Tanker",
    port: "Kolkata",
    tonnage: 105000,
    status: "Laid up",
  },
  {
    id: "v06",
    name: "MV Western Gate",
    type: "Ro-Ro",
    port: "Mumbai",
    tonnage: 31000,
    status: "Active",
  },
  {
    id: "v07",
    name: "MV Konkan Trader",
    type: "General cargo",
    port: "Goa",
    tonnage: 12500,
    status: "Active",
  },
  {
    id: "v08",
    name: "MT Bay Spirit",
    type: "Tanker",
    port: "Chennai",
    tonnage: 98000,
    status: "In dry dock",
  },
];

const statusTone = {
  Active: "success",
  "In dry dock": "warning",
  "Laid up": "neutral",
} as const;

const ROW_ACTIONS: MenuEntry[] = [
  { id: "view", label: "View", icon: ViewIcon },
  { id: "edit", label: "Edit", icon: EditIcon },
  { id: "duplicate", label: "Duplicate", icon: CopyIcon, isDisabled: true },
  { id: "sep", type: "separator" },
  { id: "delete", label: "Delete", icon: DeleteIcon, tone: "destructive" },
];

function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      className="flex flex-col gap-4 border-t border-border-subtle pt-8"
    >
      <div className="flex flex-col gap-1">
        <h2 id={`${id}-title`} className="text-section text-text-primary">
          {title}
        </h2>
        <p className="text-body-sm text-text-secondary">{description}</p>
      </div>
      {children}
    </section>
  );
}

function DataShowcase() {
  const [sort, setSort] = useState<SortDescriptor | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);
  const [state, setState] = useState<"ready" | "loading" | "empty" | "error">(
    "ready",
  );
  const [lastAction, setLastAction] = useState("none");

  const sorted = useMemo(() => {
    if (!sort) return VESSELS;
    const key = sort.columnId as "name" | "tonnage";
    const rows = [...VESSELS].sort((a, b) =>
      a[key] < b[key] ? -1 : a[key] > b[key] ? 1 : 0,
    );
    return sort.direction === "ascending" ? rows : rows.reverse();
  }, [sort]);
  const rows =
    state === "empty"
      ? []
      : sorted.slice((page - 1) * pageSize, page * pageSize);

  const columns: DataTableColumn<Vessel>[] = [
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
      id: "port",
      header: "Home port",
      cell: (row) => row.port,
      visibleFrom: "desktop",
    },
    {
      id: "tonnage",
      header: "Tonnage (DWT)",
      cell: (row) => row.tonnage.toLocaleString("en-IN"),
      isSortable: true,
      align: "end",
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <Badge tone={statusTone[row.status]}>{row.status}</Badge>,
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-48">
          <Select
            label="Table state (demo)"
            options={[
              { id: "ready", label: "Populated" },
              { id: "loading", label: "Loading" },
              { id: "empty", label: "Empty" },
              { id: "error", label: "Error" },
            ]}
            value={state}
            onChange={(id) => setState((id as typeof state) ?? "ready")}
          />
        </div>
        <output className="text-caption text-text-muted">
          Selected: {selected.size} · Last action: {lastAction}
        </output>
      </div>
      <DataTable
        label="Fleet register (sample)"
        columns={columns}
        rows={rows}
        getRowId={(row) => row.id}
        getRowLabel={(row) => row.name}
        sort={sort}
        onSortChange={setSort}
        selectionMode="multiple"
        selectedIds={selected}
        onSelectionChange={setSelected}
        isLoading={state === "loading"}
        loadingLabel="Loading vessels"
        error={
          state === "error"
            ? {
                title: "We couldn't load the vessels",
                description: "The service did not respond.",
                onRetry: () => setState("ready"),
              }
            : null
        }
        emptyState={{
          title: "No vessels yet",
          description: "Vessels you add will appear here.",
        }}
        rowActions={(row) => (
          <DropdownMenu
            trigger={
              <IconButton label={`Actions for ${row.name}`} icon={MoreIcon} />
            }
            items={ROW_ACTIONS}
            onAction={(id) => setLastAction(`${id} ${row.name}`)}
          />
        )}
        footer={
          <Pagination
            page={page}
            pageSize={pageSize}
            totalItems={state === "empty" ? 0 : VESSELS.length}
            pageSizeOptions={[5, 10, 25]}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(1);
            }}
            onPageChange={setPage}
            itemLabel="vessels"
            label="Fleet register pages"
          />
        }
      />
      <DataTable
        label="Fleet register — card layout on mobile (sample)"
        columns={columns}
        rows={VESSELS.slice(0, 3)}
        getRowId={(row) => row.id}
        mobileLayout="cards"
      />
    </div>
  );
}

function FilterShowcase() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [from, setFrom] = useState<string | null>(null);
  const count = (status ? 1 : 0) + (from ? 1 : 0);
  const filters = (
    <>
      <div className="w-full tablet:w-48">
        <Select
          label="Status"
          options={[
            { id: "active", label: "Active" },
            { id: "dry-dock", label: "In dry dock" },
            { id: "laid-up", label: "Laid up" },
          ]}
          value={status}
          onChange={setStatus}
        />
      </div>
      <div className="w-full tablet:w-48">
        <DatePicker label="Updated from" value={from} onChange={setFrom} />
      </div>
    </>
  );
  return (
    <FilterBar
      search={
        <Search
          label="Search vessels"
          isLabelHidden
          value={query}
          onChange={setQuery}
          placeholder="Search vessels"
        />
      }
      filters={filters}
      activeFilterCount={count}
      resultCount={`${VESSELS.length - count * 2} results`}
      onClear={() => {
        setStatus(null);
        setFrom(null);
      }}
    />
  );
}

export function OverlaysShowcase() {
  const [contextAction, setContextAction] = useState("none");
  const [confirmed, setConfirmed] = useState("none");
  const [notifications, setNotifications] = useState(true);
  const [time, setTime] = useState<string | null>("09:30");

  return (
    <>
      <ToastRegion queue={showcaseToasts} label="Showcase notifications" />

      <Section
        id="dialogs"
        title="Dialog"
        description="Modal container: focus trap, Escape, focus return, sizes; sheet-like on mobile."
      >
        <div className="flex flex-wrap gap-3">
          {(["sm", "md", "lg", "xl"] as const).map((size) => (
            <Dialog
              key={size}
              size={size}
              title={`Edit record (${size})`}
              description="Changes are saved when you select Save."
              trigger={<Button variant="secondary">Open {size} dialog</Button>}
              actions={(close) => (
                <>
                  <Button variant="secondary" onPress={close}>
                    Cancel
                  </Button>
                  <Button onPress={close}>Save</Button>
                </>
              )}
            >
              <div className="flex flex-col gap-4">
                <Input label="Name" defaultValue="MV Coral Star" />
                <Input label="Call sign" defaultValue="AVCS7" />
              </div>
            </Dialog>
          ))}
        </div>
      </Section>

      <Section
        id="alert-dialogs"
        title="AlertDialog"
        description="Confirmation: focus starts on Cancel; Escape cancels; the scrim never confirms."
      >
        <div className="flex flex-wrap items-center gap-3">
          <AlertDialog
            trigger={
              <Button variant="destructive" iconStart={DeleteIcon}>
                Delete record
              </Button>
            }
            title="Delete this record?"
            description="This permanently removes the record and cannot be undone."
            confirmLabel="Delete record"
            tone="destructive"
            onConfirm={() => setConfirmed("deleted")}
            onCancel={() => setConfirmed("cancelled")}
          />
          <AlertDialog
            trigger={<Button variant="secondary">Publish changes</Button>}
            title="Publish changes?"
            description="Published changes become visible to all users."
            confirmLabel="Publish"
            onConfirm={() => setConfirmed("published")}
          />
          <output className="text-caption text-text-muted">
            Last confirmation: {confirmed}
          </output>
        </div>
      </Section>

      <Section
        id="popovers"
        title="Popover"
        description="Anchored, labelled panel; Escape and outside click close it."
      >
        <div className="flex flex-wrap gap-3">
          <Popover
            trigger={<Button variant="secondary">What is DWT?</Button>}
            title="Deadweight tonnage"
          >
            The weight a vessel can carry, including cargo, fuel, stores and
            crew.
          </Popover>
          <Popover
            trigger={<Button variant="secondary">Display options</Button>}
            title="Display options"
            size="sm"
          >
            <Switch defaultSelected>Compact rows</Switch>
          </Popover>
        </div>
      </Section>

      <Section
        id="tooltips"
        title="Tooltip"
        description="Short labels for icon-only controls; shown on hover and keyboard focus."
      >
        <div className="flex flex-wrap gap-3">
          <Tooltip content="Download report">
            <IconButton
              label="Download report"
              icon={DownloadIcon}
              variant="secondary"
            />
          </Tooltip>
          <Tooltip content="Settings" placement="bottom">
            <IconButton
              label="Settings"
              icon={SettingsIcon}
              variant="secondary"
            />
          </Tooltip>
        </div>
      </Section>

      <Section
        id="drawers"
        title="Drawer"
        description="Side and bottom panels; full width on mobile."
      >
        <div className="flex flex-wrap gap-3">
          {(["left", "right", "top", "bottom"] as const).map((side) => (
            <Drawer
              key={side}
              side={side}
              title={`${side[0]!.toUpperCase()}${side.slice(1)} panel`}
              description="Contextual details and supporting workflows."
              trigger={
                <Button
                  variant="secondary"
                  iconStart={side === "left" ? MenuIcon : undefined}
                >
                  Open {side} drawer
                </Button>
              }
              actions={(close) => <Button onPress={close}>Done</Button>}
            >
              <div className="flex flex-col gap-4">
                <Input label="Reference" defaultValue="REF-2026-0412" />
                <Switch defaultSelected>Follow updates</Switch>
              </div>
            </Drawer>
          ))}
        </div>
      </Section>

      <Section
        id="dropdown-menus"
        title="Dropdown Menu"
        description="Actions from a button; arrow keys, disabled items, separators, destructive tone."
      >
        <div className="flex flex-wrap items-center gap-3">
          <DropdownMenu
            trigger={
              <Button variant="secondary" iconEnd={MoreIcon}>
                Actions
              </Button>
            }
            items={ROW_ACTIONS}
            onAction={(id) => setContextAction(`menu: ${id}`)}
          />
          <DropdownMenu
            trigger={
              <IconButton
                label="Export options"
                icon={DownloadIcon}
                variant="secondary"
              />
            }
            items={[
              {
                id: "csv",
                label: "Export CSV",
                description: "Opens in spreadsheets",
              },
              { id: "pdf", label: "Export PDF" },
            ]}
            onAction={(id) => setContextAction(`export: ${id}`)}
          />
          <output className="text-caption text-text-muted">
            Last action: {contextAction}
          </output>
        </div>
      </Section>

      <Section
        id="context-menus"
        title="Context Menu"
        description="Right-click, Shift+F10 or the Menu key; always a shortcut, never the only path."
      >
        <ContextMenu
          label="Document actions"
          items={ROW_ACTIONS}
          onAction={(id) => setContextAction(`context: ${id}`)}
        >
          <div className="flex flex-wrap items-center gap-3 rounded-lg border border-dashed border-border-strong p-4">
            <Button variant="secondary">Survey report.pdf</Button>
            <span className="text-body-sm text-text-secondary">
              Right-click or press Shift+F10 on the file.
            </span>
          </div>
        </ContextMenu>
      </Section>

      <Section
        id="toasts"
        title="Toast"
        description="Announced notifications; success/info auto-dismiss, errors persist; pause on hover or focus."
      >
        <div className="flex flex-wrap gap-3">
          <Button
            variant="secondary"
            onPress={() =>
              showToast(
                {
                  tone: "success",
                  title: "Record saved",
                  description: "All changes were saved.",
                },
                {},
                showcaseToasts,
              )
            }
          >
            Success toast
          </Button>
          <Button
            variant="secondary"
            onPress={() =>
              showToast(
                {
                  tone: "info",
                  title: "Export started",
                  description: "You'll be notified when it's ready.",
                },
                {},
                showcaseToasts,
              )
            }
          >
            Info toast
          </Button>
          <Button
            variant="secondary"
            onPress={() =>
              showToast(
                {
                  tone: "warning",
                  title: "Certificate expires soon",
                  description: "Renew within 14 days.",
                },
                {},
                showcaseToasts,
              )
            }
          >
            Warning toast
          </Button>
          <Button
            variant="secondary"
            onPress={() =>
              showToast(
                {
                  tone: "error",
                  title: "Upload failed",
                  description: "Nothing was saved. Try again.",
                },
                {},
                showcaseToasts,
              )
            }
          >
            Error toast
          </Button>
          <Button
            variant="secondary"
            onPress={() =>
              showToast(
                {
                  tone: "info",
                  title: "Record archived",
                  action: {
                    label: "Undo",
                    onAction: () => setConfirmed("undo"),
                  },
                },
                {},
                showcaseToasts,
              )
            }
          >
            Toast with action
          </Button>
        </div>
      </Section>

      <Section
        id="data-tables"
        title="DataTable"
        description="Typed, controlled table: sorting, selection, row actions, states, pagination; scroll or cards on mobile."
      >
        <DataShowcase />
      </Section>

      <Section
        id="pagination"
        title="Pagination"
        description="Server-side ready; compact on mobile."
      >
        <Pagination
          label="Pagination example"
          page={7}
          pageSize={25}
          totalItems={1284}
          onPageChange={() => {}}
          itemLabel="records"
        />
      </Section>

      <Section
        id="filter-bars"
        title="FilterBar"
        description="Search + filters + clear + result count; filters open in a Drawer on mobile."
      >
        <FilterShowcase />
      </Section>

      <Section
        id="searches"
        title="Search"
        description="Search field with clear, Escape and Enter; never searches by itself."
      >
        <div className="grid grid-cols-1 gap-6 desktop:grid-cols-2">
          <Search
            label="Search records"
            placeholder="Name, reference or port"
          />
          <Search
            label="Search (loading)"
            defaultValue="tanker"
            isLoading
            loadingLabel="Searching…"
          />
        </div>
      </Section>

      <Section
        id="radios"
        title="Radio"
        description="Radio groups: vertical and horizontal, descriptions, disabled, invalid."
      >
        <div className="grid grid-cols-1 gap-6 desktop:grid-cols-2">
          <RadioGroup
            label="Delivery mode"
            defaultValue="classroom"
            options={[
              {
                value: "classroom",
                label: "Classroom",
                description: "On campus",
              },
              {
                value: "online",
                label: "Online",
                description: "Live virtual sessions",
              },
              {
                value: "simulator",
                label: "Simulator",
                description: "Bridge simulator",
                isDisabled: true,
              },
            ]}
          />
          <RadioGroup
            label="Priority"
            orientation="horizontal"
            isInvalid
            errorMessage="Choose a priority."
            options={[
              { value: "low", label: "Low" },
              { value: "normal", label: "Normal" },
              { value: "high", label: "High" },
            ]}
          />
        </div>
      </Section>

      <Section
        id="switches"
        title="Switch"
        description="Immediate on/off settings."
      >
        <div className="flex flex-col gap-2">
          <Switch
            isSelected={notifications}
            onChange={setNotifications}
            description="Email me when records change."
          >
            Email notifications
          </Switch>
          <Switch>Compact rows</Switch>
          <Switch isInvalid errorMessage="Enable this to continue.">
            Accept retention policy
          </Switch>
          <Switch isDisabled>Beta features (unavailable)</Switch>
        </div>
      </Section>

      <Section
        id="time-pickers"
        title="TimePicker"
        description="ISO HH:mm values; en-IN 12-hour display by default; 24-hour override."
      >
        <div className="grid grid-cols-1 gap-6 desktop:grid-cols-2">
          <div className="flex flex-col gap-2">
            <TimePicker
              label="Session starts"
              value={time}
              onChange={setTime}
            />
            <output id="time-iso" className="text-caption text-text-muted">
              ISO value: {time ?? "empty"}
            </output>
          </div>
          <TimePicker
            label="Watch (24-hour)"
            hourCycle={24}
            defaultValue="16:00"
          />
          <TimePicker
            label="Office hours"
            minValue="09:00"
            maxValue="17:00"
            defaultValue="18:15"
            description="9:00 am – 5:00 pm"
          />
          <TimePicker label="Locked" defaultValue="10:00" isDisabled />
        </div>
      </Section>
    </>
  );
}
