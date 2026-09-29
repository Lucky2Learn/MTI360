# design-system/

Shared visual foundation for all four experiences. Values come from [DESIGN-SYSTEM.md](../../../DESIGN-SYSTEM.md); architecture and catalogue: [docs/architecture/design-tokens.md](../../../docs/architecture/design-tokens.md); decision: [ADR-0007](../../../docs/adr/0007-styling-tailwind-semantic-tokens.md).

| Directory | Contents | Task |
|---|---|---|
| `tokens/` | `primitives.css` (palette + derived; the only raw colours), `semantic.css` (Light / Dark mappings), `tailwind.css` (Tailwind v4 `@theme`), token and guard tests | T00-06 |
| `theme/` | Light / Dark / System preference, pre-paint script, `ThemeProvider` / `useTheme`, `ThemeSelector` | T00-06 |
| `typography/` | Self-hosted Inter (`next/font/local`) | T00-06 |
| `components/` | Core components — 07A: Button, IconButton, Card, Badge, Tabs, Kpi, Timeline, Alert, Skeleton, EmptyState, ErrorState; 07B: Field/Form, Input, Textarea, Checkbox, Select, Combobox, DatePicker, FileUpload; 07C: Overlay (internal), Dialog, AlertDialog, Popover, Tooltip, Drawer, DropdownMenu, ContextMenu, Toast, DataTable, Pagination, FilterBar, Search, RadioGroup, Switch, TimePicker; T00-08: NavigationProvider (client-side routing for React Aria links) | T00-07, T00-08 |
| `icons/` | Curated Lucide icons (the only `lucide-react` import) | T00-07 |
| `layout/` | Responsive layout primitives — Container, Stack, Inline, Grid/GridItem, Section, SplitLayout, ActionBar, Show — and the breakpoint/spacing vocabulary ([layout.md](../../../docs/architecture/layout.md)) | T00-09 |
| `lib/` | `cx()` and the shared `focusRing` / `insetFocusRing` classes | T00-07, T00-09 |
| `testing/` | `expectNoA11yViolations()` (axe) for component tests | T00-07 |
| `templates/` | Page templates T01–T18 | later |

## Rules

- Style with semantic utilities only: `bg-surface-primary`, `text-text-secondary`, `border-border-default`, `text-page-title`, `rounded-md`, `shadow-sm`, `p-4`, `tablet:` / `desktop:` / `large:`.
- No raw colours (hex, `rgb()`, `hsl()`, …) outside `tokens/primitives.css` and no `dark:` utilities — both fail `tokens/guard.test.ts`.
- No arbitrary values (`p-[17px]`, `bg-[…]`) — test-enforced since T00-07 — and no off-grid spacing (`p-7`); add a token instead. Token references such as `outline-(length:--focus-ring-width)` are allowed.
- Page layout uses `@/design-system/layout` (Grid, Stack, Inline, SplitLayout, ActionBar, Show) instead of ad-hoc flex/grid classes and scattered `hidden desktop:block` utilities.
- Screens import components from `@/design-system/components` and icons from `@/design-system/icons`; React Aria and `lucide-react` are imported only inside `components/` and `icons/` (test-enforced).
- Every component follows its contract in [docs/architecture/components.md](../../../docs/architecture/components.md) and has tests with an axe check.
- Text uses `text-*`, `link` or `*-text` tokens (≥ 4.5:1). `accent-maritime`, `accent-brass` and state colours (`success`, …) are for non-text indicators.
- Never communicate status by colour alone.
- `design-system/` imports nothing from `features/`.
