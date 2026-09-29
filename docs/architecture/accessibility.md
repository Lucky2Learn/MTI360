# Accessibility Foundation (T00-10)

MTI 360 targets **WCAG 2.2 AA** in every experience (CLAUDE.md §38). This document is the engineering contract that the design system, the application shell and every future screen follow. It builds on [components.md](components.md), [application-shell.md](application-shell.md), [layout.md](layout.md) and [design-tokens.md](design-tokens.md). It is not a certification of the whole application: each new screen verifies itself with the checklist in §14.

Principle: **native HTML first, React Aria for complex widgets, ARIA only when neither provides the semantics.** No second accessibility framework, and no custom focus traps or roles where React Aria already supplies them.

## 1. Where things live

| Concern | Mechanism |
|---|---|
| Behaviour, ARIA, keyboard, focus management of widgets | React Aria Components (ADR-0008) inside `design-system/components` |
| Focus indicator | `focusRing` / `insetFocusRing` (`design-system/lib/cx.ts`), `fieldFocus` / `fieldFocusWithin` (Field); global `:focus-visible` fallback in `app/globals.css` |
| Reduced motion | `motion-reduce:` / `motion-safe:` on every transition and animation, plus a global `prefers-reduced-motion` net in `app/globals.css` |
| Contrast | Semantic tokens with contrast tests (`tokens/tokens.test.ts`) |
| Guards | `tokens/guard.test.ts`: focus replacement, reduced-motion pairing, no positive `tabIndex`, plus the T00-06/07 guards; `eslint-plugin-jsx-a11y` recommended rules |
| Test helpers | `design-system/testing/axe.ts` (`expectNoA11yViolations`), `design-system/testing/a11y.ts` (see §12) |

## 2. Keyboard

- Everything that works with a pointer works with the keyboard. Tab and Shift+Tab follow the DOM order, which is the visual order. There is no positive `tabIndex` (guarded).
- Widget keyboard models come from React Aria and are not re-invented:
  - **Buttons and links:** Enter; buttons also Space.
  - **Checkbox and Switch:** Space.
  - **RadioGroup:** arrow keys move and select.
  - **Tabs:** arrow keys, Home/End.
  - **Menus:** arrow keys, Home/End, type-ahead, Enter; Escape closes.
  - **ContextMenu:** Shift+F10 or the Menu key.
  - **Select:** Enter, Space or ArrowDown opens; arrow keys move; Enter selects.
  - **Combobox:** type, or ArrowDown to open; arrow keys move (virtual focus); Enter selects; Escape closes.
  - **DatePicker and TimePicker:** Tab moves between segments; ArrowUp/Down change values; the calendar grid uses arrow keys and Page Up/Down; Escape closes.
  - **Dialog, AlertDialog, Drawer, Popover:** Escape closes.
  - **Toast region:** F6 landmark navigation.
  - **Command search:** Ctrl+K / ⌘K.
- A single-page scrollable region (the DataTable scroll area) is focusable so it can be scrolled with the keyboard.

## 3. Focus

- **Visible focus everywhere** (2.4.7). All focus uses the token ring: semantic `focus-ring`, 2px wide (`--focus-ring-width`), offset 2px (`--focus-ring-offset`).
  - `focusRing` is the standard ring. It uses `data-focus-visible` and `:focus-visible`, so it appears for keyboard focus, not on mouse click.
  - `insetFocusRing` is the same ring drawn inside the element. Use it for focusable elements inside a parent that clips overflow: the DataTable scroll region and Tabs in their scrolling tab list.
  - `fieldFocus` / `fieldFocusWithin` put a ring on text fields for any focus (typing needs it).
  - Listbox options and menu items get a background plus an inset ring.
  - The global base-layer `:focus-visible` rule gives any element that does not style its own focus (plain links, native controls) the token ring instead of the browser default. Component utilities override it.
- **`outline-none` is never used without a replacement** in the same class statement. The only exceptions are programmatic focus containers (overlay surfaces, dialog panels, listbox and menu containers, the toast region, `main#main-content`), each annotated with an `a11y-focus:` comment (guarded).
- **Focus rings are never clipped.** Use `insetFocusRing` inside overflow containers. Chromium verification checks every focus stop for clipping.
- **Focus is never lost.** When a control disappears or becomes disabled because it was used, move focus to the logical next control. Pagination does this: after First/Last it focuses the current page button. Focus never lands in `aria-hidden` or `inert` content.
- **Overlays** (React Aria, not custom traps):

  | Overlay | Initial focus | Contained | Escape | Focus return |
  |---|---|---|---|---|
  | Dialog, Drawer | first focusable element | yes (modal) | closes | trigger |
  | AlertDialog | **Cancel** (safest action) | yes | cancels | trigger |
  | Popover | the popover (a labelled dialog) | yes, page is inert | closes | trigger |
  | DropdownMenu, ContextMenu | first item | menu keyboard model | closes | trigger / target |
  | Select, DatePicker calendar | selected option / date | popover | closes | trigger |
  | Combobox | stays in the input (virtual focus) | Tab closes the list first | closes | input |

- The skip link is the first tab stop on every experience. It becomes visible on focus (44px) and moves focus to `main#main-content` (`tabIndex -1`, no visible ring on the container itself).

## 4. Accessible names and descriptions

- Every interactive control has an accessible name (`expectNamedControls` in tests).
- Icon-only controls use `IconButton label` (required prop). Icons are always `aria-hidden`.
- Visible labels are real `<label>` elements or `aria-labelledby`. Placeholders are never labels.
- Descriptions and errors are linked with `aria-describedby` (React Aria `slot="description"` / `FieldError`).
- Name the thing, not the widget: for example "Drop or paste files for Continuous Discharge Certificate (CDC)", not React Aria's internal "DropZone".
- Tooltips add a description to a control that already has a name. They never carry essential information or form instructions, and they appear on keyboard focus as well as on hover.

## 5. Forms and errors

- Use the 07B components inside `Form`. Do not create a second validation architecture.
- **Required:** a visible `*` (hidden from assistive technology) plus the programmatic `required` / `aria-required`, and a "* Required field" note on the form (INC-23).
- **Invalid:** `aria-invalid="true"`, an error message linked via `aria-describedby`, an error icon plus text (never colour alone), and the invalid border.
- **On submit:** the first invalid field receives focus. Server errors (`Form validationErrors`) map to the same fields and clear when edited.
- **Success:** opt-in `successMessage`, shown as icon plus text.
- **Character count:** `showCount` renders a visible "n / max" linked as a description (`Textarea`).
- **Upload problems:** rejected files and the reason are announced politely (FileUpload status region).

## 6. Status messages and live regions

| Situation | Semantics |
|---|---|
| Non-critical status (loading, result counts, saved) | `role="status"` (polite) |
| Critical, must interrupt (error alert that blocks the task) | `Alert tone="error"` → `role="alert"` (assertive); use sparingly |
| Transient confirmation | `toast.*()`: region landmark, polite; error toasts and toasts with an action never auto-dismiss (2.2.1); reachable with F6; dismiss button named |
| Page / section loading | `LoadingRegion` / `ShellLoading`: `role="status"`, `aria-busy`, one label; skeletons are `aria-hidden` (never announce every skeleton) |
| Table loading → error / empty | DataTable's persistent status announces "Loading …", then the error title or the empty-state title |
| Async search / suggestions | Search and Combobox keep a persistent status with the loading text |
| Pending button | `Button isPending`: stays focusable, `aria-disabled`, React Aria announces the pending state change; prevents duplicate submission |
| Route change | Next.js route announcer (page `<title>`) |

Rules:

- A live region must **exist before its text changes**. Keep the element mounted and change its content. A region mounted together with its text is often not announced.
- Announce outcomes, not every UI change. Do not wrap whole sections in live regions.

## 7. Dialogs and menus

- `Dialog` is the generic modal (`role="dialog"`). `AlertDialog` is the confirmation (`role="alertdialog"`). They remain distinct. Both have a title (their accessible name) and an optional description (`aria-describedby`).
- Destructive confirmations: a destructive tone plus explicit verb labels ("Delete record"), Cancel focused first, and the scrim does not dismiss.
- The Drawer has a named close button, and so does the Dialog unless an action closes it.
- Menus: `role="menu"` / `menuitem` from React Aria. Disabled items expose `aria-disabled`. Destructive items use an icon plus text, not colour alone.

## 8. Tables and pagination

- DataTable is a semantic `<table>` with a (visually hidden) caption. It has column headers, a row header column, `aria-sort` on sortable headers (icon plus state, never colour alone), checkbox selection with names ("Select MV Coral Star"), row actions in named buttons or menus, and horizontal scrolling inside a focusable, labelled region. Loading, empty and error states are announced (§6).
- Pagination is a named `<nav>`. The current page has `aria-current="page"` plus a different shape (bordered), so it does not rely on colour. Unavailable controls are disabled. Page buttons are named "Page n". Focus is kept (§3).

## 9. Reduced motion

- Every `transition-*` / `animate-*` utility is paired with `motion-reduce:` or `motion-safe:` on the same line (guarded).
- `app/globals.css` sets near-zero animation and transition durations and turns off smooth scrolling under `prefers-reduced-motion: reduce`. End states and events still happen, so state changes (open, closed, selected) stay visible.
- Spinners use `motion-safe:animate-spin`. They are static under reduced motion, and the text still conveys the state.

## 10. Contrast and colour

- Text uses `text-*`, `link` and `*-text` tokens (≥ 4.5:1). Non-text indicators use state colours, `accent-maritime`, `brand-primary`, `border-strong` and `focus-ring` (≥ 3:1). All are tested in Light and Dark (`tokens.test.ts`, with `brand-primary` non-text pairs added in T00-10).
- Control boundaries use `border-strong` (inputs, selects, checkboxes, radios, switches, secondary buttons). `border-subtle` / `border-default` / `ai-border` are **decorative only**: cards, dividers and table rules. They must not be the only boundary of an interactive control.
- Status is never conveyed by colour alone. Pair it with an icon, text, weight or shape.
- Disabled controls use native `disabled` / `aria-disabled` plus reduced opacity. They are exempt from contrast requirements (1.4.3).
- **Known exception, INC-24:** in Dark mode, all four `*-text` state tokens on `surface-elevated` (dialogs, drawers, popovers, menus) are below 4.5:1: error 3.79, info 4.03, success 4.19, warning 4.22 (all ≥ 3:1). Destructive menu items avoid it, and Badges and Alerts use their own state surfaces. Field error and success messages inside a Dialog, Drawer or Popover in Dark mode are still affected until the token task resolves INC-24. The failing pairs are pinned in `tokens.test.ts`.

## 11. Structure: landmarks, headings, links and buttons

- **Landmarks** (verified per experience):
  - one `banner` (the app header or the public-site header);
  - uniquely named `navigation` landmarks (the experience navigation, "Breadcrumb", pagination);
  - one `main#main-content`;
  - `contentinfo` on the public site;
  - the toast `region`.
  - Complementary (`aside`) is only used at the top level, never inside `main`.
- **Headings:**
  - Exactly one `h1` per page: the `PageHeader` title.
  - Page sections are `h2` (`Section`); sub-sections and cards inside a section are `h3`; do not skip levels going down.
  - Choose the level by structure, not by size (the type scale is independent: `Section` h2 uses `text-card-heading`/`text-section`).
  - Overlays start their own outline (the dialog title).
  - `expectHeadingOutline` asserts this in tests.
- **Links vs buttons:**
  - Links navigate: `next/link`, or `Button href`, which renders a React Aria link and navigates client-side through `NavigationProvider`.
  - Buttons act: `Button` / `IconButton`.
  - Menu items that navigate use `href`.
  - No clickable `div`/`span` (jsx-a11y enforces this).
- `lang="en"` on `<html>`, and every page has a unique `<title>` ("Page · Experience · MTI 360").

## 12. Touch targets and mobile

- 44px targets below the tablet breakpoint: `control-height-md` grows to 44px, and shell navigation, drawer items, menu and listbox options, pagination and breadcrumb links (T00-10) all meet it.
- **Exceptions** (all ≥ 24px, WCAG 2.5.8 AA):
  - `size="sm"` buttons (32px) in dense secondary contexts (card headers, toolbars). Never use them for the primary mobile action.
  - Auxiliary buttons inside a 44px field (calendar, clear search, combobox chevron).
  - DataTable sort headers.
  - Native radio and checkbox inputs, whose wrapping `<label>` is the 44px target.
- No horizontal page overflow, and no clipped focus at 390px (T00-09 plus T00-10 verification).

## 13. Testing strategy

1. **Guards (static):** `tokens/guard.test.ts` (focus replacement, reduced-motion pairing, no positive `tabIndex`, arbitrary values, raw colours, `dark:`, library boundaries). `jsx-a11y` recommended rules in lint. `globals.test.ts` pins the base-layer rules.
2. **Component tests (jsdom):** each component's own tests plus `components/accessibility.test.tsx`. That suite checks overlay keyboard, focus and Escape/return; menu, tooltip and alert-dialog semantics; named controls; the token ring; semantic state; and keyboard operation. `ShellAccessibility.test.tsx` checks landmarks, headings, the skip link and names for every experience. Helpers in `design-system/testing`:
   - `expectNoA11yViolations`: axe. `color-contrast` and `region` are disabled in jsdom only; they run in Chromium.
   - `expectNamedControls`.
   - `tabSequence`.
   - `expectFocusContained`.
   - `expectFocusRing`.
   - `expectHeadingOutline`.
3. **Browser (headless Chromium, production image):**
   - Light and Dark at 390/768/1024/1440, plus System.
   - Keyboard walk of every focus stop: visible ring, ring contrast ≥ 3:1, not clipped, never in hidden content, 44px on mobile.
   - axe (WCAG 2.2 AA plus best practice, including contrast).
   - The overlay matrix, reduced motion, and production gating.
   - The script lives outside the repository, as in T00-07…T00-09, so no Playwright dependency is needed.
4. **Assistive-technology spot checks** with NVDA/VoiceOver are recommended before production release (Phase 16/17). They are not automated here.

## 14. Screen checklist

Every future MTI 360 screen verifies:

- [ ] Keyboard accessible: every action works with the keyboard, in a logical order
- [ ] Visible focus: the token ring, never clipped
- [ ] Accessible names for every control, including icon-only ones
- [ ] Labels and descriptions associated
- [ ] Correct semantic HTML (native first, React Aria widgets, ARIA only when necessary)
- [ ] Heading hierarchy: one h1 (PageHeader), h2 sections, no skipped levels
- [ ] Landmark structure: shell landmarks, named navigation, nothing outside landmarks
- [ ] Form validation accessible: required, invalid, linked errors, first invalid field focused
- [ ] Errors announced appropriately (§6)
- [ ] Loading state accessible: one status, skeletons hidden, no duplicate actions
- [ ] No colour-only meaning
- [ ] WCAG AA contrast (tokens only; mind INC-24 on elevated surfaces in Dark)
- [ ] 44px mobile targets (exceptions per §12)
- [ ] Reduced motion
- [ ] No horizontal overflow at 390px
- [ ] Screen-reader-meaningful structure and order
- [ ] Dialog and menu focus behaviour (entry, containment, Escape, return)
- [ ] Mobile accessibility (drawer navigation, stacked actions, filters in the Drawer)
- [ ] Light, Dark and System verified

## 15. Known exceptions

| Exception | Where | Why | Mitigation |
|---|---|---|---|
| axe `aria-hidden-focus`, `page-has-heading-one`, `region`, `scrollable-region-focusable` **while a Combobox list is open** | Combobox (07B) | React Aria's `useComboBox` hides the page with `aria-hidden` (its `ariaHideOutside` call does not use the `inert` option, and no prop exposes it), so the header, `h1` and landmarks are hidden. The options use virtual focus (`aria-activedescendant`), so the scrolling list has no focusable descendant | Tab closes the list before focus moves, and focus never reaches hidden content. Arrow keys scroll the active option into view. Axe is 0 once the list is closed. Verified in Chromium in both themes at 390 and 1024. Revisit when React Aria exposes inert hiding for comboboxes |
| Dark `*-text` state text on `surface-elevated` < 4.5:1 (3.79–4.22:1) | tokens (INC-24) | Needs a token change (stop condition) | Destructive menu items avoid it; Badges and Alerts are unaffected. Field error and success messages inside dialogs, drawers and popovers in Dark mode remain affected until INC-24 is resolved. **Decision needed:** a token task |
| 32px `sm` controls, in-field auxiliary buttons, 24px-plus non-44px targets listed in §12 | Button/IconButton `sm`, DatePicker, Search, Combobox, DataTable | Density in secondary contexts | ≥ 24px (WCAG 2.5.8 AA). Primary mobile actions use `md` / `lg` |
| Collapsed sidebar rail has no visible tooltip | Shell (T00-08) | Tooltip needs a React Aria pressable trigger. Rail items are native links | The accessible names are present. The full labels are available in the drawer |
