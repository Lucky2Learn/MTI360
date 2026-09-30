import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DeleteIcon, SettingsIcon } from "@/design-system/icons";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import {
  expectContrast,
  THEMES,
  type ThemeTokens,
} from "@/design-system/testing/contrast";

import {
  Alert,
  AlertDialog,
  Button,
  createToastQueue,
  Dialog,
  Drawer,
  DropdownMenu,
  ErrorState,
  IconButton,
  Input,
  Popover,
  showToast,
  Switch,
  ToastRegion,
} from "./index";

import type { ReactElement, ReactNode } from "react";

// State text and indicator contrast as rendered (T00-10A, INC-24;
// docs/architecture/accessibility.md §10). jsdom cannot compute colours, so
// each rendered state utility (text-<state>-text, text-<state>) is paired with
// the nearest ancestor background utility and both are resolved from the
// shipped token CSS in Light and Dark. Text needs ≥ 4.5:1, icons ≥ 3:1.
// Overlays (Dialog, AlertDialog, Drawer, Popover, menus, toasts) render on
// surface-elevated — the surface INC-24 failed on in Dark.

const STATES = "(?:error|success|warning|info)";
const STATE_UTILITY = new RegExp(`^text-(${STATES}(?:-text)?)$`);
const BACKGROUND_UTILITY = new RegExp(
  `^bg-((?:background|surface)-[a-z]+|${STATES}-surface)$`,
);

type Pair = { foreground: string; background: string; minimum: number };

const utilities = (element: Element): string[] =>
  (element.getAttribute("class") ?? "").split(/\s+/);

/** The unprefixed token behind the first utility matching `pattern`. */
function tokenOf(element: Element, pattern: RegExp): string | undefined {
  for (const utility of utilities(element)) {
    const token = utility.match(pattern)?.[1];
    if (token) return token;
  }
  return undefined;
}

/** Every rendered state text / indicator paired with the surface behind it. */
function statePairs(root: Element): Pair[] {
  return [root, ...root.querySelectorAll("[class]")].flatMap((element) => {
    const foreground = tokenOf(element, STATE_UTILITY);
    if (!foreground) return [];
    let background: string | undefined;
    for (
      let node: Element | null = element;
      node && !background;
      node = node.parentElement
    ) {
      background = tokenOf(node, BACKGROUND_UTILITY);
    }
    return [
      {
        foreground,
        // Nothing painted behind it: the page background.
        background: background ?? "background-primary",
        minimum: foreground.endsWith("-text") ? 4.5 : 3,
      },
    ];
  });
}

function expectStatePairs(
  root: Element,
  theme: ThemeTokens,
  expected: string[],
): void {
  const pairs = statePairs(root);
  const rendered = pairs.map((p) => `${p.foreground} on ${p.background}`);
  for (const pair of expected) expect(rendered).toContain(pair);
  for (const { foreground, background, minimum } of pairs) {
    expectContrast(theme, foreground, background, minimum);
  }
}

function setTheme(name: string): void {
  document.documentElement.dataset.theme = name.toLowerCase();
}

afterEach(() => {
  delete document.documentElement.dataset.theme;
});

// --- Overlays: field validation and status text on surface-elevated -------------

type OverlayCase = {
  name: string;
  trigger: string;
  role: "dialog" | "alertdialog";
  wrap: (children: ReactNode) => ReactElement;
};

const OVERLAYS: OverlayCase[] = [
  {
    name: "Dialog",
    trigger: "Edit cadet",
    role: "dialog",
    wrap: (children) => (
      <Dialog
        title="Edit cadet"
        trigger={<Button>Edit cadet</Button>}
        defaultOpen
      >
        {children}
      </Dialog>
    ),
  },
  {
    name: "AlertDialog",
    trigger: "Withdraw application",
    role: "alertdialog",
    wrap: (children) => (
      <AlertDialog
        title="Withdraw this application?"
        description="The applicant will need to apply again for this batch."
        confirmLabel="Withdraw application"
        tone="destructive"
        onConfirm={vi.fn()}
        trigger={<Button>Withdraw application</Button>}
        defaultOpen
      >
        {children}
      </AlertDialog>
    ),
  },
  {
    name: "Drawer",
    trigger: "Batch filters",
    role: "dialog",
    wrap: (children) => (
      <Drawer
        title="Batch filters"
        trigger={<Button>Batch filters</Button>}
        defaultOpen
      >
        {children}
      </Drawer>
    ),
  },
  {
    name: "Popover",
    trigger: "Quick edit",
    role: "dialog",
    wrap: (children) => (
      <Popover
        title="Quick edit"
        trigger={<Button variant="secondary">Quick edit</Button>}
        defaultOpen
      >
        {children}
      </Popover>
    ),
  },
];

const VALIDATION = (
  <>
    <Input
      label="CDC number"
      isInvalid
      errorMessage="Enter the Continuous Discharge Certificate number."
    />
    <Input
      label="INDoS number"
      defaultValue="08ZL1234"
      successMessage="INDoS number verified."
    />
    <Switch isInvalid errorMessage="Confirm the medical fitness declaration.">
      Medically fit for sea service
    </Switch>
  </>
);

describe.each(THEMES)("state text in overlays — %s", (theme, tokens) => {
  it.each(OVERLAYS)(
    "$name: field error and success text meet AA on the overlay surface",
    async ({ role, wrap }) => {
      setTheme(theme);
      render(wrap(VALIDATION));
      const overlay = await screen.findByRole(role);
      expect(
        overlay.closest(".bg-surface-elevated") ??
          overlay.querySelector(".bg-surface-elevated"),
      ).not.toBeNull();
      await screen.findByText("INDoS number verified.");
      expectStatePairs(overlay.ownerDocument.body, tokens, [
        "error-text on surface-elevated",
        "success-text on surface-elevated",
      ]);
      await expectNoA11yViolations(document.body);
    },
  );

  it.each(["info", "success", "warning", "error"] as const)(
    "Alert %s inside a Dialog keeps its own state surface",
    async (tone) => {
      setTheme(theme);
      render(
        OVERLAYS[0]!.wrap(
          <Alert tone={tone} title="Batch DNS-24 schedule updated">
            Seat allocation for Deck Cadets changed.
          </Alert>,
        ),
      );
      const overlay = await screen.findByRole("dialog");
      expectStatePairs(overlay, tokens, [`${tone}-text on ${tone}-surface`]);
      await expectNoA11yViolations(document.body);
    },
  );

  it("destructive menu item: error icon on surface-elevated, error text when focused", async () => {
    setTheme(theme);
    const user = userEvent.setup();
    render(
      <DropdownMenu
        trigger={<IconButton label="Certificate actions" icon={SettingsIcon} />}
        items={[
          { id: "view", label: "View certificate" },
          {
            id: "revoke",
            label: "Revoke certificate",
            icon: DeleteIcon,
            tone: "destructive",
          },
        ]}
        onAction={vi.fn()}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Certificate actions" }),
    );
    const menu = await screen.findByRole("menu");
    const pairs = statePairs(menu).map(
      (p) => `${p.foreground} on ${p.background}`,
    );
    expect(pairs).toContain("error on surface-elevated");
    expectStatePairs(menu, tokens, []);
    // Focused destructive item: error-text on error-surface.
    expectContrast(tokens, "error-text", "error-surface", 4.5);
    await expectNoA11yViolations(document.body);
  });
});

// --- Page-level state components ---------------------------------------------------

describe.each(THEMES)("state components — %s", (theme, tokens) => {
  it.each(["info", "success", "warning", "error"] as const)(
    "Alert %s text meets AA on its state surface",
    async (tone) => {
      setTheme(theme);
      const { container } = render(
        <Alert tone={tone} title="Fee instalment due">
          Second instalment for Pre-Sea Training is due on 15 October.
        </Alert>,
      );
      expectStatePairs(container, tokens, [`${tone}-text on ${tone}-surface`]);
      await expectNoA11yViolations(container);
    },
  );

  it("ErrorState icon meets 3:1 on the error surface", async () => {
    setTheme(theme);
    const { container } = render(
      <ErrorState
        title="Batch timetable could not be loaded"
        description="Check your connection and try again."
        onRetry={vi.fn()}
      />,
    );
    expectStatePairs(container, tokens, ["error on error-surface"]);
    await expectNoA11yViolations(container);
  });

  it.each(["info", "success", "warning", "error"] as const)(
    "Toast %s indicator meets 3:1 on surface-elevated",
    async (tone) => {
      setTheme(theme);
      const queue = createToastQueue();
      render(<ToastRegion queue={queue} />);
      act(() => {
        showToast({ tone, title: "STCW certificate uploaded" }, {}, queue);
      });
      const region = await screen.findByRole("region", {
        name: "Notifications",
      });
      await waitFor(() => expect(statePairs(region).length).toBeGreaterThan(0));
      expectStatePairs(region, tokens, [`${tone} on surface-elevated`]);
      await expectNoA11yViolations(document.body);
    },
  );

  it("field validation on a page surface meets AA", async () => {
    setTheme(theme);
    const { container } = render(<div>{VALIDATION}</div>);
    expectStatePairs(container, tokens, [
      "error-text on background-primary",
      "success-text on background-primary",
    ]);
    await expectNoA11yViolations(container);
  });
});
