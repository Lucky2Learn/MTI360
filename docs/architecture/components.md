# Component Library

- **Status:** T00-07A merged (PR #7); T00-07B (forms) implemented (2026-09-27); T00-07C (overlays and data) not started
- **Decision basis:** T00-07 proposal decisions D1–D14 (approved); [ADR-0008](../adr/0008-headless-primitives-and-icons.md) (React Aria Components, Lucide); [ADR-0007](../adr/0007-styling-tailwind-semantic-tokens.md) (tokens)
- **Code:** `frontend/src/design-system/components/`, `icons/`, `lib/`, `testing/`; showcase `frontend/src/app/design-system/`
- **Related:** [DESIGN-SYSTEM.md](../../DESIGN-SYSTEM.md) §41–§62, §69–§75; [design-tokens.md](design-tokens.md); [spec-inconsistencies.md](spec-inconsistencies.md) (INC-18 … INC-23)

## 1. Delivery plan (decision D1)

T00-07 is delivered in three slices, each with its own branch, review, pull request and merge commit.

| Slice | Components | Status |
|---|---|---|
| **07A** Infrastructure, actions, display, states | Button, IconButton, Card, Badge, Tabs, KPI, Timeline, Alert, Skeleton, EmptyState, ErrorState, `/design-system` showcase | Merged (PR #7) |
| **07B** Forms | Field foundation + Form, Input, Textarea, Checkbox, Select, Combobox, DatePicker, FileUpload | Implemented |
| **07C** Overlays and data | Modal, Dialog, Drawer, Toast, DataTable, Pagination, FilterBar, ChartCard | Not started |

Deferred beyond T00-07 (D12): Radio group (the ThemeSelector pattern exists), Switch, TimePicker, Search input, PermissionGate / AccessDenied (ErrorState provides the permission presentation). Shell components are T00-08.

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
| Visible focus via `focusRing` (semantic `focus-ring`, `--focus-ring-width` 2px, offset 2px) | tests + browser check |
| Motion only with `motion-safe:` or disabled by `motion-reduce:` | browser check (reduced motion) |
| Axe on every component test (`testing/axe.ts`; contrast and landmark rules checked in the browser) | tests |

Server-component compatible (no client code): Card, Badge, KPI, Timeline, Alert, Skeleton, EmptyState. Client components: Button, IconButton, Tabs, ErrorState and all form components (07B).

Links rendered by `Button href` are React Aria links (plain `<a href>` navigation). Client-side routing integration (`RouterProvider`) is added with the application shell (T00-08).

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
| Accessibility | tablist/tab/tabpanel roles, arrow keys, Home/End, disabled tabs skipped, panel labelled by its tab |

### KPI

| Aspect | Contract |
|---|---|
| Purpose | Label · Value · Trend · Comparison · Context (§51) |
| Props | `label`, `value` (pre-formatted: locale/currency by the caller, D10), `trend` {`direction` up/down/flat, `value`, `sentiment` positive/negative/neutral}, `comparison`, `context`, `icon` |
| Theme | trend colour follows the caller's **sentiment**, not the direction (overdue fees up = negative) |
| Responsive | the KPI fills its grid cell; grids stack on mobile (the caller's layout) |
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
| Known axe note | while the popover is open React Aria hides the rest of the page with `aria-hidden` (not inert), which axe reports as `aria-hidden-focus`. Tab closes the popover before focus moves, so focus never reaches hidden content (verified in the browser) |

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
| Accessibility | labelled group; "Choose file(s)" button (Enter/Space); focusable drop zone with paste support; rules text linked as a description; rejections in a polite status region; labelled "Remove {file}" buttons (44px below `tablet`) |

## 4. Showcase — `/design-system` (decision D8)

- Every 07A and 07B component in its variants and states, with realistic maritime sample data and the theme selector; a Student enquiry form (two columns from `desktop`, §84 actions, simulated server validation — nothing is submitted).
- Available only when `APP_ENV` is `development` or `test`; any other value or an invalid configuration returns **404** (fail closed). `robots: noindex, nofollow`. Rendered per request (`force-dynamic`), so the runtime `APP_ENV` of the container decides.
- Residual risk: `APP_ENV` defaults to `development` when unset (T00-04), so a deployment that omits it would expose this data-free gallery; deployed environments must set `APP_ENV` (environments.md).

## 5. Verification (T00-07A)

- Unit and component tests (Vitest, Testing Library, user-event, axe) for every component, the tokens and the guards; showcase gate matrix.
- Headless Chromium on the production image (`APP_ENV=test`): Light and Dark at 390 / 768 / 1024 / 1440 — axe (WCAG 2.2 AA including contrast) with 0 violations, no overflow, no console warnings, no external requests; keyboard activation, focus ring in the token colour, tabs keyboard model, pending/disabled; 44px controls on mobile; reduced motion; neutral page regression; `APP_ENV=production` returns 404 for `/design-system`.

## 6. Verification (T00-07B)

- Unit tests: Field/Form (blocked submit, first invalid field focused, server errors mapped and cleared once edited), controlled/uncontrolled and `FormData` for every control, keyboard models (Select, Combobox, Checkbox, DatePicker segments and calendar), ISO helpers, `en-IN` segment order, Monday-first default and Sunday override, server-render output, `validateFiles` matrix, FileUpload accept/reject/remove and no object URLs; axe with popovers open. jsdom needed no polyfills (D8).
- Headless Chromium on the production image (`APP_ENV=test`): the 07A suite plus Select, Combobox and calendar popovers in Light and Dark at 390 and 1024 (axe, within viewport, option min-height), DatePicker typing → ISO, calendar keyboard, Escape focus return, Sunday override, FileUpload valid/denied/double-extension/oversized and no object URLs, enquiry form (first invalid focus, server error mapping, Space on checkbox), 44px controls on mobile, reduced motion, async combobox — 129/129 checks.
