# Component Library

- **Status:** T00-07A merged (PR #7); T00-07B merged (PR #8); T00-07C (overlays, data and interaction controls) implemented (2026-09-27)
- **Decision basis:** T00-07 proposal decisions D1–D14 (approved); [ADR-0008](../adr/0008-headless-primitives-and-icons.md) (React Aria Components, Lucide); [ADR-0007](../adr/0007-styling-tailwind-semantic-tokens.md) (tokens)
- **Code:** `frontend/src/design-system/components/`, `icons/`, `lib/`, `testing/`; showcase `frontend/src/app/design-system/`
- **Related:** [DESIGN-SYSTEM.md](../../DESIGN-SYSTEM.md) §41–§62, §69–§75; [design-tokens.md](design-tokens.md); [spec-inconsistencies.md](spec-inconsistencies.md) (INC-18 … INC-25)

## 1. Delivery plan (decision D1)

T00-07 is delivered in three slices, each with its own branch, review, pull request and merge commit.

| Slice | Components | Status |
|---|---|---|
| **07A** Infrastructure, actions, display, states | Button, IconButton, Card, Badge, Tabs, KPI, Timeline, Alert, Skeleton, EmptyState, ErrorState, `/design-system` showcase | Merged (PR #7) |
| **07B** Forms | Field foundation + Form, Input, Textarea, Checkbox, Select, Combobox, DatePicker, FileUpload | Merged (PR #8) |
| **07C** Overlays, data and interaction controls | Dialog (Modal), AlertDialog, Popover, Tooltip, Drawer, DropdownMenu, ContextMenu, Toast, DataTable, Pagination, FilterBar, Search, RadioGroup, Switch, TimePicker | Implemented |

The T00-07C implementation prompt brought Search, Radio group, Switch and TimePicker (deferred by D12) into 07C and did not include ChartCard (INC-19). Still deferred: ChartCard, PermissionGate / AccessDenied (ErrorState provides the permission presentation). Shell components are T00-08 ([application-shell.md](application-shell.md)).

## 2. Architecture and rules

```text
React Aria Components (behaviour, ARIA, keyboard, focus)      Lucide via design-system/icons
        ↓                                                            ↓
MTI 360 component (semantic/component tokens through Tailwind utilities, typed variant maps)
        ↓
screens — import only from "@/design-system/components"
```

| Rule | Enforcement |
|---|---|
| Semantic or component tokens only; no raw colours | `tokens/guard.test.ts` |
| No `dark:` utilities; theme changes come from semantic tokens | guard |
| No Tailwind arbitrary values (`p-[17px]`, `bg-[…]`, `[prop:value]`); token references `x-(--token)` and arbitrary *variants* (`has-[:focus-visible]:`) are allowed | guard (with detector fixtures) |
| `lucide-react` imported only in `design-system/icons` | guard |
| React Aria packages imported only in `design-system/components` | guard |
| `dangerouslySetInnerHTML` only for the pre-paint theme script | guard |
| Class joining with `cx()`; variants as `Record<Variant, string>` maps (no clsx/cva/tailwind-merge, D4) | review |
| Visible focus via `focusRing` (semantic `focus-ring`, `--focus-ring-width` 2px, offset 2px); `insetFocusRing` (same ring, drawn inside) for focusable containers within a clipping parent (T00-09); global `:focus-visible` fallback; `outline-none` only with a replacement or an `a11y-focus:` justification (T00-10) | tests + guard + browser check |
| Every transition/animation paired with `motion-reduce:` / `motion-safe:` on the same line; no positive `tabIndex` (T00-10) | guard |
| Motion only with `motion-safe:` or disabled by `motion-reduce:` | browser check (reduced motion) |
| Axe on every component test (`testing/axe.ts`; contrast and landmark rules checked in the browser); shared accessibility assertions in `testing/a11y.ts` and the cross-component contract in `components/accessibility.test.tsx` (T00-10, [accessibility.md](accessibility.md)) | tests |

Server-component compatible (no client code): Card, Badge, KPI, Timeline, Alert, Skeleton, EmptyState. Client components: Button, IconButton, Tabs, ErrorState, all form components (07B) and all 07C components.

Links rendered by `Button href` are React Aria links (plain `<a href>` navigation). Since T00-08, `NavigationProvider` (`components/Router`, a framework-neutral wrapper of React Aria's `RouterProvider`) is mounted by the shell's `ExperienceFrame` with the Next.js router, so these links navigate client-side inside the experiences; outside it they fall back to normal browser navigation.

## 3. Component contracts (DESIGN-SYSTEM.md §73 / §74)

### Button

| Aspect | Contract |
|---|---|
| Purpose | Primary and secondary actions; `href` renders navigation styled as a button |
| Variants | `primary` (brand-primary / brand-primary-hover, text-inverse), `secondary` (surface + border-strong), `tertiary` (text-style: link colour, underline on hover — D13), `ghost` (transparent, surface-hover — D13), `destructive` (error-strong), `success` (success-strong; the specification success colour is 4.49:1 with white) |
| Props | `variant`, `size` (sm 32 / md 40 / lg 44 px), `iconStart`, `iconEnd`, `fullWidth`, `isPending`, `isDisabled`, `onPress`, `href`/`target`/`rel`, React Aria button props |
| States | default, hover, pressed, focus-visible, disabled (opacity 50%, not focusable), pending (spinner, label kept, presses blocked) |
| Light / Dark | via semantic tokens; hover of filled destructive/success is an elevation change (shadow-md) |
| Responsive | medium height becomes 44px below `tablet` (touch target); `fullWidth` for stacked mobile actions |
| Accessibility | native `<button>`/`<a>`; Enter/Space; decorative icons `aria-hidden`; `target=_blank` gets `rel="noopener noreferrer"` |
| Interaction / errors | destructive buttons never confirm by themselves — confirmation is Dialog (07C, §62) |

### IconButton

| Aspect | Contract |
|---|---|
| Purpose | Icon-only actions (settings, close, add) |
| Variants / sizes | `primary`, `secondary`, `ghost` (default), `destructive`; square `sm`/`md`/`lg` control heights |
| Props | `label` (**required**, becomes `aria-label`; missing label fails type-checking), `icon`, `isPending`, `isDisabled`, `onPress` |
| Responsive | medium is 44×44 below `tablet` |
| Accessibility | named by `label`; icon hidden; visible tooltip comes with the overlay components (07C) |

### Card (CardHeader, CardBody, CardFooter)

| Aspect | Contract |
|---|---|
| Purpose | Grouping when it helps (§43) — not a default wrapper |
| Props | `as` (div/section/article), `elevation` (none/sm/md), `padding` (none/md/lg), `aria-labelledby`/`aria-label`; header: `title`, `titleAs` (h2–h4), `titleId`, `description`, `actions` |
| Light / Dark | surface-primary + border-subtle; elevation tokens (Dark: near-zero shadow) |
| Responsive | padding 16 → 24 px from `tablet`; header actions wrap below the title |
| Accessibility | real headings; section/article cards labelled by their title |

### Badge

| Aspect | Contract |
|---|---|
| Purpose | Compact status or tag (§50) |
| Tones | neutral, info, success, warning, error, ai |
| Props | `children` (text, required), `tone`, `icon` (override or `false`) |
| States / theme | `*-surface` background, `*-text` text (≥ 4.5:1), state colour border |
| Accessibility | status = text + icon + colour, never colour alone; icon decorative |

### Tabs (Tabs, TabList, Tab, TabPanel)

| Aspect | Contract |
|---|---|
| Purpose | Closely related views only (§46) |
| Props | Tabs: `selectedKey`/`defaultSelectedKey`/`onSelectionChange`; TabList: `aria-label` (required); Tab: `id`, `isDisabled`; TabPanel: `id` |
| States | default, hover, selected (Sea Glass indicator bar + semibold), focus-visible, disabled |
| Responsive | the tab list scrolls horizontally on narrow screens (native scrollbar as the overflow cue) |
| Accessibility | tablist/tab/tabpanel roles, arrow keys, Home/End, disabled tabs skipped, panel labelled by its tab; the focus ring is drawn inside each tab (`insetFocusRing`) so the scrolling list cannot clip it (T00-10) |

### KPI

| Aspect | Contract |
|---|---|
| Purpose | Label · Value · Trend · Comparison · Context (§51) |
| Props | `label`, `value` (pre-formatted: locale/currency by the caller, D10), `trend` {`direction` up/down/flat, `value`, `sentiment` positive/negative/neutral}, `comparison`, `context`, `icon` |
| Theme | trend colour follows the caller's **sentiment**, not the direction (overdue fees up = negative) |
| Responsive | the KPI fills its grid cell; grids stack on mobile (the caller's layout, [layout.md](layout.md)). A value wider than the cell wraps instead of spilling (T00-09); prefer compact formats ("₹12.4 Cr") in multi-column rows |
| Accessibility | labelled group; trend in words for screen readers ("Increased by 8.4%"), arrow + sign visually — never colour alone |

### Timeline

| Aspect | Contract |
|---|---|
| Purpose | Ordered events (activity, later AuditTimeline) |
| Props | `aria-label`, `items` [{`id`, `title`, `timestamp` (ISO), `timestampLabel` (formatted), `actor`, `description`, `tone`, `icon`}] |
| Accessibility | `<ol>`/`<li>`, `<time dateTime>`, tone announced as hidden text ("Warning: …"), distinct icon shapes |

### Alert

| Aspect | Contract |
|---|---|
| Purpose | Inline, concise, actionable message (§49) |
| Tones | info, success, warning, error |
| Props | `tone`, `title`, `children`, `action` |
| Responsive | action moves below the text on mobile |
| Accessibility | `role="alert"` for errors (assertive), `role="status"` otherwise; icon shape + text |

### Skeleton (Skeleton, SkeletonText, SkeletonCard, SkeletonTableRows, LoadingRegion)

| Aspect | Contract |
|---|---|
| Purpose | Layout-stable loading placeholders (§58) |
| Props | Skeleton: `width` (full, 3/4, 1/2, 1/3, 1/4), `height` (text, heading, control, block), `shape` (rounded, circle); presets take `lines`, `rows`, `columns`; LoadingRegion: `label` |
| Accessibility | shapes `aria-hidden`; LoadingRegion is `role="status"`, `aria-busy`, announces its label once; pulse only without reduced motion |

### EmptyState

| Aspect | Contract |
|---|---|
| Purpose | What is empty, why, what next (§59, UI-SCREENS §10) |
| Props | `title`, `description`, `icon` (default Inbox; subtle maritime icons such as Compass allowed), `primaryAction`, `secondaryAction`, `titleAs` |
| Responsive | actions stack full-width on mobile (primary first), inline from `tablet` |

### ErrorState

| Aspect | Contract |
|---|---|
| Purpose | What happened, what was saved, what to do, can I retry (§60); permission-restricted presentation (§57) |
| Props | `kind` (error, permission), `title`, `description`, `savedState`, `onRetry`/`retryLabel`/`isRetrying`, `backHref`/`backLabel`, `supportHref`/`supportLabel`, `reference`, `titleAs` |
| Security | renders only caller-supplied, user-safe text; `Error` objects do not type-check; no stack traces, SQL or provider details (CLAUDE.md §37); `reference` is a correlation ID for support. The authorization decision is always server-side |
| Responsive | the actions stack full width on mobile and form a row from `tablet` that wraps in narrow containers (T00-09) |
| Accessibility | labelled region; actions are real buttons/links |

## 3B. Form component contracts (T00-07B)

Decisions (T00-07B proposal, approved): D1 `value`/`defaultValue`/`onChange` with React Aria-style booleans; D2 DatePicker ISO strings; D3 Monday-first product default with `firstDayOfWeek` override; D4 visible `*` + programmatic required; D5 native validation + `validate` + `Form validationErrors`; D6 opt-in success; D7 FileUpload UX-only validation; D8 no polyfills needed; D9 popovers on all sizes; D10 no new tokens or dependencies; D11 showcase and enquiry form; D12 INC-20 update, INC-22, INC-23.

**Shared API conventions (D1).** Values: `value` / `defaultValue` / `onChange` (strings, option ids, ISO dates, `File[]`). Booleans: `isRequired`, `isDisabled`, `isReadOnly`, `isInvalid` (Checkbox: `isSelected` / `defaultSelected`). Messages: `description`, `errorMessage` (string or `(validation) => string`), `successMessage` (opt-in). `name` submits with native forms (FileUpload excepted — the caller uploads files).

### Field foundation and Form

| Aspect | Contract |
|---|---|
| Pieces | `FieldLabel` (label + visible `*` hidden from assistive technology when required, D4), `FieldDescription` (description slot), `FieldErrorMessage` (React Aria `FieldError`: error icon + text in `error-text`, only while invalid), `FieldSuccessMessage` (icon + text in `success-text`, opt-in, D6), shared control classes (`border-strong` 3:1, hover, `border-error` when invalid, disabled/read-only surfaces, focus ring on every focus for text entry) |
| Form | React Aria `Form` with `validationBehavior="native"` by default (D5): invalid submits are blocked and the first invalid field receives focus; errors appear after submit or when an edit is committed (blur). `validationErrors={{ fieldName: message }}` shows server-side errors on the matching fields until the edit is committed |
| Accessibility | label ↔ control, description and error via `aria-describedby`, `aria-invalid`, `aria-required`/`required`; never colour alone (icon + text + border) |

### Input

| Aspect | Contract |
|---|---|
| Purpose | Single-line text (§42) |
| Props | `label`, `type` (text, email, tel, url, password, search), `placeholder`, `icon` (decorative), React Aria TextField props (`value`, `defaultValue`, `onChange`, `name`, `isRequired`, `isDisabled`, `isReadOnly`, `isInvalid`, `validate`, `minLength`, `maxLength`, `pattern`, `autoComplete`, `inputMode`), `description`, `errorMessage`, `successMessage` |
| States | default, hover, focus, filled, disabled, read-only, error, success |
| Responsive | full width of its grid cell; 44px tall below `tablet` |

### Textarea

| Aspect | Contract |
|---|---|
| Props | as Input (no `type`/`icon`) + `rows` (default 4), `showCount` with `maxLength` |
| Behaviour | vertical resize; "n / max characters" count linked as a description (not announced per keystroke); works controlled and uncontrolled |

### Checkbox

| Aspect | Contract |
|---|---|
| Built on | React Aria 1.21 `CheckboxField` + `CheckboxButton` |
| Props | `children` (label), `isSelected`/`defaultSelected`/`onChange(boolean)`, `isIndeterminate`, `name`, `value`, `isRequired`, `isInvalid`, `isDisabled`, `description`, `errorMessage` |
| Accessibility | native checkbox, Space toggles, label row is the target (44px below `tablet`), indeterminate exposed as mixed, check/minus mark (not colour alone) |

### Select

| Aspect | Contract |
|---|---|
| Purpose | One option from a short, known list |
| Props | `label`, `options` [{`id`, `label`, `description?`, `isDisabled?`}], `value`/`defaultValue`/`onChange(id \| null)`, `placeholder`, `name`, `isRequired`, `isDisabled`, `isInvalid`, `description`, `errorMessage`, `successMessage` |
| Keyboard | Enter/Space/ArrowDown open; arrows, Home/End, type-ahead; Enter selects; Escape closes and returns focus |
| Popover (D9) | portalled, `surface-elevated` + `shadow-lg`, trigger width, viewport-constrained, scrolls; options min 44px below `tablet` (40px above); selection = check mark + `surface-selected` + weight |
| Forms | hidden native select submits the option id |

### Combobox

| Aspect | Contract |
|---|---|
| Purpose | Type to filter a longer list |
| Props | as Select + `filtering` (`contains` default, or `manual`), `inputValue`/`defaultInputValue`/`onInputChange`, `isLoading`, `emptyMessage`, `loadingMessage`, `allowsCustomValue` (default false) |
| Async (manual) | the caller owns the text and supplies already-filtered options; the component never fetches. Loading: spinner + polite status text **inside the popover** (React Aria hides content outside an open popover; its ListBox does not forward `aria-busy`) |
| Behaviour | empty-result message in the listbox; custom text reverts to the selected option on blur; selected id in `FormData` |
| Known axe note | while the list is open React Aria's `useComboBox` hides the rest of the page with `aria-hidden` (its `ariaHideOutside` call does not use the inert option; no prop exposes it). axe then reports `aria-hidden-focus`, `page-has-heading-one` and `region`, and — because options use virtual focus (`aria-activedescendant`) — `scrollable-region-focusable` for the scrolling list. Tab closes the list before focus moves, focus never reaches hidden content, arrow keys scroll the active option into view, and axe is 0 once closed (re-verified in Chromium in T00-10; [accessibility.md](accessibility.md) §15). No axe exclusion exists in the repository |

### DatePicker

| Aspect | Contract |
|---|---|
| Value (D2) | ISO `YYYY-MM-DD` strings (`null` = empty); `@internationalized/date` stays internal; invalid ISO input is treated as empty. Dates only — no times, no time zones |
| Locale | `locale` prop, default **`en-IN`** (DD/MM/YYYY with leading zeros) applied through `I18nProvider`, so server and client render identically |
| First day of week (D3) | **Monday by MTI 360 product default** (`MTI360_FIRST_DAY_OF_WEEK`), deliberately independent of the locale's own convention (CLDR `en-IN` starts on Sunday). Override with `firstDayOfWeek` when a screen requires another convention |
| Validation | `isRequired`, `minValue`/`maxValue` (ISO), `isDateUnavailable(iso)`, `validate(iso)`, server errors via `Form`; React Aria's range messages |
| Keyboard | segments are spinbuttons (digits, Up/Down, Tab); calendar button → grid (arrows, PageUp/PageDown, Enter, Escape returns focus) |
| Visuals | selected = `brand-primary` + `text-inverse`; today underlined + semibold; unavailable struck through; outside-month muted; 44px cells below `tablet`; popover fits 390px |

### FileUpload

| Aspect | Contract |
|---|---|
| Purpose | Select files for a later upload by the caller — **no upload transport** |
| Props | `label`, `accept` (**required**: [{`label`, `mimeTypes`, `extensions`}]), `maxSize` (**required**, bytes), `maxFiles` (default 1), `value`/`defaultValue`/`onChange(File[])`, `onReject(rejections)`, `isRequired`, `isDisabled`, `isInvalid`, `errorMessage`, `description`, `locale` |
| Client checks (UX only, D7) | extension (last one, case-insensitive) **and** browser-reported MIME must match the same `accept` entry; permanent deny list (`DENIED_EXTENSIONS`: executables, installers, scripts, HTML/SVG/XML, macro-enabled Office formats) regardless of `accept`; empty files; size; count; duplicates; names with control characters, path separators or > 255 characters |
| Security boundary | client checks are not a security control. The server remains authoritative: extension + sniffed MIME + size, filename sanitisation, content validation, malware scan, tenant-scoped storage (CLAUDE.md §50, ARCHITECTURE.md §49). No previews, no object URLs, no reading of file contents; names rendered as text only |
| Accessibility | labelled group; "Choose file(s)" button (Enter/Space); focusable drop zone with paste support, named "Drop or paste files for {label}" (T00-10; previously React Aria's internal "DropZone"); rules text linked as a description; rejections in a polite status region; labelled "Remove {file}" buttons (44px below `tablet`) |

## 3C. Overlay, data and interaction contracts (T00-07C)

**Shared overlay infrastructure** (`components/Overlay/`, internal). `overlay.ts` holds the shared surfaces: `popoverSurface` (`surface-elevated`, `border-default`, `shadow-lg`, `z-(--z-dropdown)`), `modalBackdrop` (`overlay-scrim`) and `panelSurface`; entry fades use `starting:` (`@starting-style`) and are removed by `motion-reduce:transition-none`. The 07B Select, Combobox and DatePicker popovers now use `popoverSurface` (styling consolidation only; API and behaviour unchanged). `PanelDialog` is the shared header / scrolling body / actions layout for Dialog, AlertDialog and Drawer (`title` is the accessible name, `description` is linked with `aria-describedby`, optional close IconButton, `children` / `actions` may be `(close) => ReactNode`). Layering uses the existing tokens: dropdown, popover and menu 200, drawer 300, modal 400, toast and tooltip 500. No new tokens.

**Common overlay behaviour.** React Aria provides focus containment and restoration, Escape, outside-interaction dismissal, scroll locking for modals, portalling, viewport containment (`containerPadding` 16px) and `aria-hidden` on content outside modals. Open state is uncontrolled with a `trigger`, or controlled with `isOpen` / `onOpenChange`.

### Dialog (Modal)

| Aspect | Contract |
|---|---|
| Purpose | Generic modal for focused tasks and short forms (§48). "Modal" in TASKS.md is this component (INC-18) |
| Props | `title`, `description`, `children`, `actions`, `showCloseButton` (default true), `closeLabel`, `size` (`sm` / `md` default / `lg` / `xl` → `max-w-sm` / `lg` / `2xl` / `4xl` from `tablet`), `trigger`, `isOpen` / `defaultOpen` / `onOpenChange`, `isDismissable` (scrim click, default true) |
| Behaviour | focus moves into the dialog and is trapped; Escape always closes; focus returns to the trigger; page scroll locked |
| Responsive | full width minus the 16px gutter on mobile with a scrolling body and visible actions; size caps from `tablet` |

### AlertDialog

| Aspect | Contract |
|---|---|
| Purpose | Confirmation of a consequential action (§48, §86) |
| Props | `title`, `description` (the consequence), `confirmLabel` (explicit, never "OK"), `cancelLabel` (default "Cancel"), `tone` (`default` / `destructive`), `onConfirm`, `onCancel`, `isPending` (keeps it open), `trigger` or `isOpen` / `defaultOpen` / `onOpenChange`, `children` |
| Behaviour | `role="alertdialog"`; **Cancel receives initial focus** (the safest action; scoped `jsx-a11y/no-autofocus` exception); a scrim click does not dismiss; Escape cancels; no close button; confirm closes it when uncontrolled |

### Popover

| Aspect | Contract |
|---|---|
| Purpose | Anchored supplementary content or a small interactive group |
| Props | `trigger`, `title` or `aria-label` (an accessible name is required), `children`, `placement` (default `bottom start`), `size` (`sm` 256px / `md` 320px), `isOpen` / `defaultOpen` / `onOpenChange` |
| Behaviour | the React Aria popover itself is the labelled dialog (T00-10: no nested Dialog, so its hidden screen-reader "Dismiss" buttons are inside the dialog); focus moves in and is contained while the page is inert; flips and shifts inside the viewport; Escape and outside interaction close it; focus returns to the trigger |

### Tooltip

| Aspect | Contract |
|---|---|
| Purpose | Short visible label for icon-only or truncated controls — never essential information |
| Props | `content` (a few words), `children` (a focusable trigger with its own accessible name), `placement`, `delay` (hover, default 600 ms), `isDisabled` |
| Behaviour | shows on hover after the delay and immediately on keyboard focus; Escape, blur and pointer leave hide it; `aria-describedby` on the trigger; `brand-primary` surface with `text-inverse` |

### Drawer

| Aspect | Contract |
|---|---|
| Purpose | Modal side, top or bottom panel: mobile filters, contextual and detail panels, mobile navigation (T00-08) (§47) |
| Props | as Dialog (close label default "Close panel") + `side` (`left` / `right` default / `top` / `bottom`), `size` (`sm` / `md` / `lg` width from `tablet` for left/right) |
| Responsive | left/right: full width on mobile, token width from `tablet`; top/bottom: full width, leaving 64px of the page visible; the slide-in is removed under reduced motion |

### DropdownMenu and ContextMenu

| Aspect | Contract |
|---|---|
| Items | `MenuEntry[]`: `{ id, label, description?, icon?, isDisabled?, tone?: "default" \| "destructive" }` or `{ id, type: "separator" }`; `onAction(id)` |
| DropdownMenu | `trigger` (a named Button or IconButton; the menu is labelled by it — menu-button pattern), `items`, `onAction`, `placement`, `isOpen` / `onOpenChange` |
| ContextMenu | `label` (menu name), `items`, `onAction`, `children` (the region). Opens on right-click at the pointer, or with Shift+F10 / the ContextMenu key at the focused element; focus returns to the element focused before opening. A shortcut only — every action must also be reachable another way (for example a row DropdownMenu) |
| Keyboard | arrows (wrapping), Home/End, type-ahead, Enter/Space, Escape; opening with the keyboard focuses the first item; disabled items are skipped |
| Visuals | items 44px below `tablet`, 40px above; destructive = error-coloured icon at rest and `error-text` on `error-surface` when focused. The label stays `text-primary` at rest; this was chosen when Dark `error-text` on `surface-elevated` was 3.79:1. INC-24 was resolved in T00-10A (now 4.72:1), and the rest-state design is unchanged |

### Toast

| Aspect | Contract |
|---|---|
| API | `toast.success` / `info` / `warning` / `error(title, { description?, action?, timeout?, onClose? })`, `toast.dismiss(key)`, `showToast(content, options, queue)`, `createToastQueue()` (max 3 visible), `ToastRegion({ queue?, label = "Notifications" })` |
| Timing (WCAG 2.2.1) | success and info 5 s, warning 8 s; **error toasts and toasts with an action persist** until dismissed; timers pause while hovered or focused |
| Accessibility | landmark region (F6 — fixed in T00-10: the region is re-mounted when the first toast appears so React Aria registers the landmark), announced on arrival, tone icon + title (not colour alone), labelled "Dismiss notification" button, focus restored when the last toast closes |
| Layout | fixed at the bottom; full width minus gutters on mobile, 384px at the bottom end from `tablet`; `z-(--z-toast)` |
| Notes | built on React Aria's `UNSTABLE_Toast*` exports (1.21.1 pinned); the MTI 360 API insulates screens from upstream changes (INC-25). The global region is mounted by the application shell (T00-08) |

### DataTable

| Aspect | Contract |
|---|---|
| Purpose | Typed, controlled table foundation for T02 Data List (§44). It never fetches; the application owns data, sorting, selection and paging (server-side ready) |
| Props | `label` (caption), `columns` (`id`, `header`, `cell(row)`, `isSortable`, `align`, `isRowHeader`, `visibleFrom`), `rows`, `getRowId`, `getRowLabel`, `sort` / `onSortChange`, `selectionMode` (`none` / `single` / `multiple`), `selectedIds` / `onSelectionChange`, `rowActions(row)`, `rowActionsLabel`, `isLoading` / `loadingLabel` / `loadingRows`, `error` (`title`, `description`, `onRetry`, `reference`), `emptyState`, `footer`, `mobileLayout` (`scroll` default / `cards`) |
| Sorting | header buttons cycle ascending → descending → unsorted; `aria-sort` + icon |
| Selection | the shared Checkbox; "Select all rows" with an indeterminate state; per row "Select {label}" |
| States | loading (skeleton rows, `aria-busy`), error (ErrorState + retry), empty (EmptyState); one persistent polite status announces "Loading …" and then the error or empty title (T00-10) |
| Responsive | `scroll`: the table scrolls inside a focusable, labelled region (the page never overflows) and columns can be hidden below `tablet` / `desktop`; `cards`: each row becomes a card below `tablet`. The region's focus ring is drawn inside it (`insetFocusRing`) because the rounded frame clips overflow (T00-09) |

### Pagination

| Aspect | Contract |
|---|---|
| Props | `page` (1-based), `pageSize`, `totalItems`, `onPageChange`, `pageSizeOptions` + `onPageSizeChange` (rows-per-page Select), `label` (navigation name; unique on a page), `itemLabel`, `locale` (default `en-IN` number formatting) |
| Behaviour | first / previous / next / last and page numbers with ellipses (`pageItems`); the current page has `aria-current="page"`; "Showing a–b of n" summary; compact "Page x of y" below `tablet`; when a pressed control becomes disabled (first/last page reached), focus moves to the current page button or the remaining page control instead of `<body>` (T00-10) |

### FilterBar

| Aspect | Contract |
|---|---|
| Props | `search`, `filters`, `activeFilterCount`, `resultCount` (pre-formatted, announced politely), `onClear`, `onApply` (explicit apply), `label` |
| Behaviour | composition only — no filter state and no business filters. Inline from `tablet`; on mobile a "Filters (n)" button opens the filters in a bottom Drawer with Clear and Apply/Done |

### Search

| Aspect | Contract |
|---|---|
| Props | React Aria SearchField props (`value` / `defaultValue` / `onChange`, `onSubmit`, `onClear`, `name`, `isDisabled`) + `label`, `isLabelHidden`, `placeholder`, `description`, `isLoading` / `loadingLabel`, `suggestions` slot |
| Behaviour | `type="search"` with a clear button; Escape clears, Enter submits; never searches or debounces by itself; 44px below `tablet`; the loading status stays mounted so it is announced (T00-10) |

### RadioGroup

| Aspect | Contract |
|---|---|
| Props | React Aria RadioGroup props (`value` / `defaultValue` / `onChange`, `name`, `orientation`, `isRequired`, `isDisabled`, `isInvalid`, `validate`) + `label`, `options` (`value`, `label`, `description?`, `isDisabled?`), `description`, `errorMessage` |
| Behaviour | one Tab stop; arrow keys move and select; selected = ring + dot + weight; rows 44px below `tablet`; the value is in `FormData` |

### Switch

| Aspect | Contract |
|---|---|
| Purpose | An on/off setting that applies immediately (use Checkbox for choices submitted with a form) |
| Props | React Aria Switch props (`isSelected` / `defaultSelected` / `onChange`, `name`, `isDisabled`) + `children` (label), `description`, `isInvalid` + `errorMessage` (linked; React Aria's Switch has no validation state) |
| Visuals | `role="switch"`; thumb position + check mark, not colour alone; 44px row below `tablet` |

### TimePicker

| Aspect | Contract |
|---|---|
| Value | ISO `"HH:mm"` strings (24-hour, minute precision; `null` = empty); `@internationalized/date` stays internal; **no dates and no time zones** (INC-20). `FormData` receives React Aria's `"HH:mm:ss"` |
| Props | `label`, `value` / `defaultValue` / `onChange`, `minValue` / `maxValue` (ISO), `validate(iso)`, `hourCycle` (12 / 24; `en-IN` default is 12-hour with leading zeros), `locale` (default `en-IN`), `name`, `isRequired`, `isDisabled`, `description`, `errorMessage`, `successMessage` |
| Keyboard | segments are spinbuttons (digits, Up/Down, Tab, `a` / `p`); keyboard-first — React Aria has no time list |
| Server rendering | literal segments normalise Unicode spaces (Node's ICU emits U+202F before am/pm, browsers may emit U+0020), so server and client text match and hydration does not fail |

## 4. Showcase — `/design-system` (decision D8)

- Every 07A, 07B and 07C component in its variants and states (07C sections in `showcase-overlays.tsx`, with a showcase-only toast queue and region), with realistic maritime sample data and the theme selector; a Student enquiry form (two columns from `desktop`, §84 actions, simulated server validation — nothing is submitted).
- T00-09 adds the layout sections (`showcase-layout.tsx`: breakpoints, Container, Stack, Inline, Grid, Section, two-column layout, responsive visibility) and `/design-system/layout`, a generic page inside the real application shell (dashboard, data, detail and form layouts with long content). Layout contracts: [layout.md](layout.md).
- Available only when `APP_ENV` is `development` or `test` (both `/design-system` and `/design-system/layout`); any other value or an invalid configuration returns **404** (fail closed). `robots: noindex, nofollow`. Rendered per request (`force-dynamic`), so the runtime `APP_ENV` of the container decides.
- Residual risk: `APP_ENV` defaults to `development` when unset (T00-04), so a deployment that omits it would expose this data-free gallery; deployed environments must set `APP_ENV` (environments.md).

## 5. Verification (T00-07A)

- Unit and component tests (Vitest, Testing Library, user-event, axe) for every component, the tokens and the guards; showcase gate matrix.
- Headless Chromium on the production image (`APP_ENV=test`): Light and Dark at 390 / 768 / 1024 / 1440 — axe (WCAG 2.2 AA including contrast) with 0 violations, no overflow, no console warnings, no external requests; keyboard activation, focus ring in the token colour, tabs keyboard model, pending/disabled; 44px controls on mobile; reduced motion; neutral page regression; `APP_ENV=production` returns 404 for `/design-system`.

## 6. Verification (T00-07B)

- Unit tests: Field/Form (blocked submit, first invalid field focused, server errors mapped and cleared once edited), controlled/uncontrolled and `FormData` for every control, keyboard models (Select, Combobox, Checkbox, DatePicker segments and calendar), ISO helpers, `en-IN` segment order, Monday-first default and Sunday override, server-render output, `validateFiles` matrix, FileUpload accept/reject/remove and no object URLs; axe with popovers open. jsdom needed no polyfills (D8).
- Headless Chromium on the production image (`APP_ENV=test`): the 07A suite plus Select, Combobox and calendar popovers in Light and Dark at 390 and 1024 (axe, within viewport, option min-height), DatePicker typing → ISO, calendar keyboard, Escape focus return, Sunday override, FileUpload valid/denied/double-extension/oversized and no object URLs, enquiry form (first invalid focus, server error mapping, Space on checkbox), 44px controls on mobile, reduced motion, async combobox — 129/129 checks.

## 7. Verification (T00-07C)

- Unit tests for every 07C component, with axe while open: Dialog sizes, focus trap and return, Escape, scrim dismissal; AlertDialog Cancel focus, non-dismissable scrim, pending; Popover and Tooltip labelling; Drawer sides and scroll lock; DropdownMenu and ContextMenu keyboard models, Shift+F10, destructive tone, focus return; Toast queue, timing defaults, persistence, dismiss; DataTable sort cycle, single and multiple selection with indeterminate select-all, row actions, loading/empty/error, card layout; Pagination items and page size; FilterBar inline and mobile Drawer; Search clear/Escape/Enter; RadioGroup, Switch, TimePicker (ISO helpers, `en-IN` segments, 24-hour override, min/max/required + `FormData`, literal normalisation).
- Headless Chromium on the production image (`APP_ENV=test`): the 07A and 07B suites plus, in Light and Dark at 390 / 768 / 1024 / 1440, Dialog, AlertDialog, Drawer, DropdownMenu, ContextMenu and Toast within the viewport with axe 0, focus trap and restoration, Escape, no page overflow, no console errors and no hydration errors; tooltip hover and focus, context menu via Shift+F10, DataTable sorting, selection, row actions and states, pagination, the mobile FilterBar Drawer, 44px controls on mobile and reduced motion — 343/343 checks. No axe exclusions were added for 07C (the only scoped exclusion remains the 07B Combobox note above).
