# Component Library

- **Status:** T00-07A implemented (2026-09-27); T00-07B (forms) and T00-07C (overlays and data) not started
- **Decision basis:** T00-07 proposal decisions D1–D14 (approved); [ADR-0008](../adr/0008-headless-primitives-and-icons.md) (React Aria Components, Lucide); [ADR-0007](../adr/0007-styling-tailwind-semantic-tokens.md) (tokens)
- **Code:** `frontend/src/design-system/components/`, `icons/`, `lib/`, `testing/`; showcase `frontend/src/app/design-system/`
- **Related:** [DESIGN-SYSTEM.md](../../DESIGN-SYSTEM.md) §41–§62, §69–§75; [design-tokens.md](design-tokens.md); [spec-inconsistencies.md](spec-inconsistencies.md) (INC-18 … INC-21)

## 1. Delivery plan (decision D1)

T00-07 is delivered in three slices, each with its own branch, review, pull request and merge commit.

| Slice | Components | Status |
|---|---|---|
| **07A** Infrastructure, actions, display, states | Button, IconButton, Card, Badge, Tabs, KPI, Timeline, Alert, Skeleton, EmptyState, ErrorState, `/design-system` showcase | Implemented |
| **07B** Forms | Field (internal), Input, Textarea, Checkbox, Select, Combobox, DatePicker, FileUpload | Not started |
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

Server-component compatible (no client code): Card, Badge, KPI, Timeline, Alert, Skeleton, EmptyState. Client components: Button, IconButton, Tabs, ErrorState.

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

## 4. Showcase — `/design-system` (decision D8)

- Every 07A component in its variants and states, with realistic maritime sample data and the theme selector.
- Available only when `APP_ENV` is `development` or `test`; any other value or an invalid configuration returns **404** (fail closed). `robots: noindex, nofollow`. Rendered per request (`force-dynamic`), so the runtime `APP_ENV` of the container decides.
- Residual risk: `APP_ENV` defaults to `development` when unset (T00-04), so a deployment that omits it would expose this data-free gallery; deployed environments must set `APP_ENV` (environments.md).

## 5. Verification (T00-07A)

- Unit and component tests (Vitest, Testing Library, user-event, axe) for every component, the tokens and the guards; showcase gate matrix.
- Headless Chromium on the production image (`APP_ENV=test`): Light and Dark at 390 / 768 / 1024 / 1440 — axe (WCAG 2.2 AA including contrast) with 0 violations, no overflow, no console warnings, no external requests; keyboard activation, focus ring in the token colour, tabs keyboard model, pending/disabled; 44px controls on mobile; reduced motion; neutral page regression; `APP_ENV=production` returns 404 for `/design-system`.
