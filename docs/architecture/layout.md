# Responsive Layout Foundation (T00-09)

Layout primitives and the conventions every screen follows so that pages behave consistently from 390px to 1440px+ without inventing their own layout rules. Code: `frontend/src/design-system/layout/` (imported from `@/design-system/layout`). Page structure (`PageContainer`, `PageHeader`, `PageContent`) stays in the application shell (`@/shells`, [application-shell.md](application-shell.md)) and is composed from these primitives. Showcase: `/design-system` (layout sections) and `/design-system/layout` (a generic page inside the real shell), both development/test only.

## 1. Breakpoints

The approved tiers from DESIGN-SYSTEM.md §21, defined once in `tokens/tailwind.css` (unchanged by T00-09):

| Tier | Width | Tailwind prefix |
|---|---|---|
| Mobile | 390–767 | none (base, mobile-first) |
| Tablet | 768–1023 | `tablet:` |
| Desktop | 1024–1439 | `desktop:` |
| Large | 1440+ | `large:` |

Responsive props take either one value or a value per tier (`Responsive<T>`): `columns={{ base: 1, tablet: 2, large: 4 }}`. Each tier applies from its width up. Class names are written out literally in `responsive.ts` so Tailwind finds them; never build utility names with template strings.

Breakpoints are **viewport** breakpoints. Inside the Platform and Tenant shells the sidebar takes 256px from desktop (64px rail on tablet), so at 1024 the content column is about 700px wide. Choose column counts for the content column, not the viewport: for example, a 4-up KPI row starts at `large`, with 2 columns at tablet and desktop.

## 2. Primitives

| Primitive | Purpose | Key props |
|---|---|---|
| `Container` | Centres content, caps the width, applies the page gutter | `width` narrow / standard / wide / full, `gutter`, `as` |
| `Stack` | Vertical flow | `gap`, `align`, `as` (div, section, article, ul, ol) |
| `Inline` | Horizontal flow that wraps; each child is capped to the row width | `gap`, `align`, `justify`, `wrap`, `stackBelow` tablet / desktop, `as` |
| `Grid` / `GridItem` | Equal columns per breakpoint; spans per breakpoint | `columns` (1–6, 12), `gap`, `align`, `as` (incl. ul, ol, dl) · `span` (1–12, full) |
| `Section` | Titled block: `<section>` named by its h2/h3 (a plain `<div>` without a title), description, actions | `title`, `titleAs`, `description`, `actions`, `gap` |
| `SplitLayout` | Primary + secondary columns, stacked below a breakpoint | `ratio` 1:1 / 2:1 / 3:1, `stackBelow` tablet / desktop / large, `secondaryPosition` end / start |
| `ActionBar` | Action area of forms, sections and panels | `align` start / end / between, `divider`, `aria-label` (makes it a group) |
| `Show` | Responsive visibility, CSS only | `from`, `below` (tablet / desktop / large), `as` div / span |

All primitives are server-component compatible, accept no `className` (typed variants only, as in the component library), and use only design tokens. Every flex/grid primitive sets `min-w-0` on itself and its children, so long content wraps or truncates inside its cell instead of widening the page.

Not built, deliberately: `PageLayout` (it is `PageContainer` + `PageHeader` + `PageContent` from T00-08), `SidebarLayout` / `ContentLayout` (covered by `SplitLayout` and `Container`), `AspectRatio` (no consumer yet), container queries (they would add thresholds beyond the approved breakpoints).

## 3. Spacing

Gaps come from the 4px scale (DESIGN-SYSTEM.md §20). No arbitrary values.

| Gap | Size | Usage (§20) |
|---|---|---|
| `2xs` | 4px | micro |
| `xs` | 8px | compact, e.g. badges, buttons |
| `sm` | 12px | small, e.g. toolbar controls (Inline default) |
| `md` | 16px | standard (Stack default) |
| `lg` | 24px | card/panel, grid cells (Grid default) |
| `xl` | 24px → 32px from tablet | between page sections |
| `2xl` | 32px → 48px from tablet | major sections |

`PageContainer` separates the header from the content by 24 → 32px. `PageContent` separates sections by 24 → 32px, the same as `xl`.

## 4. Content width

Choose the width by content type; there is no single max-width for every screen.

| Width | Max | Use for |
|---|---|---|
| `narrow` | 48rem (768px) | Focused forms, settings, single-task flows |
| `standard` | 72rem (1152px) | Most pages, detail pages, Student Portal, public site |
| `wide` | 80rem (1280px) | Dashboards, lists, data tables (Platform and Tenant defaults) |
| `full` | none | Workspaces: Kanban, communication inbox, workflow builder |

The page gutter is 16px on mobile, 24px on tablet and 32px from desktop. `PageContainer width` accepts the same values; `narrow` was added in T00-09 without changing the API. Text-heavy blocks inside wider pages should cap their line length (for example `max-w-2xl` on descriptions). DESIGN-SYSTEM.md §82 gives 1200–1440px as typical desktop content width; see INC-29.

## 5. Page patterns

Page structure (CLAUDE.md §31):

```text
ApplicationShell
  └── PageContainer (width)
        ├── PageHeader  breadcrumbs → h1 + status → description → actions → tabs/filters
        └── PageContent (sections 24 → 32px apart)
              └── Section → Grid / Stack / SplitLayout / DataTable / Form
```

**Page header and action areas.** Put the primary action last. On mobile, actions are full width and stacked with the primary on top (44px controls). From tablet they sit beside the title while the title keeps at least 24rem, and wrap onto their own row below it otherwise. `PageHeader`, `Section` and `ActionBar` share this behaviour. Nothing is shrunk to fit.

**Dashboard.** KPIs: `Grid columns={{ base: 1, tablet: 2, large: 4 }}` (inside the shell). Charts: `Grid columns={{ base: 1, desktop: 2 }}`. Tables: full width below. Use compact formats for large figures in multi-column KPI rows (e.g. "₹12.4 Cr"); `Kpi` wraps an oversized value rather than letting it spill.

**Data / list.** `Section` (title, table-level actions such as Export) → `FilterBar` → `DataTable` with `Pagination` in its footer. Page-level primary actions belong in `PageHeader`. `FilterBar` already moves filters into its Drawer on mobile; do not build another. `DataTable` scrolls horizontally inside its own focusable region (never the page); hide low-priority columns with `visibleFrom`, or use `mobileLayout="cards"` for record lists.

**Detail.** `PageHeader` (status badge) → `SplitLayout` with primary (record, facts in `Grid as="dl"`, tabs) and secondary (summary, status, related items, next steps with `ActionBar`); stacked below desktop. Use `secondaryPosition="start"` only when the secondary content should come first in the reading order as well.

**Form.** Wrap it in `Container width="narrow"` for focused flows. Use `Grid columns={{ base: 1, desktop: 2 }}` for fields and `GridItem span="full"` for long fields (address, notes), then an `ActionBar divider`. Use the 07B components unchanged. A two-column form is appropriate only when fields are short and independent.

## 6. Responsive visibility

Use `Show` for alternative presentations at different widths, not scattered `hidden desktop:block` utilities in screens. It uses CSS only (`display: none` / `contents`), with no `window.innerWidth` or resize listeners, so server and client markup match. Hidden content is removed from the accessibility tree, so every width must still offer the same information and actions in some form. Components with built-in responsive behaviour (Breadcrumbs, FilterBar, DataTable, Pagination, the shell) keep their own internal rules.

## 7. Overflow and long content

- There is no page-level horizontal overflow, and overflow is never hidden globally. Wide content scrolls inside its own container (DataTable region, Tabs list).
- Long names, e-mails and titles wrap (`break-words`, `min-w-0` on flex/grid children). Breadcrumb labels truncate. KPI values wrap (`wrap-anywhere`).
- Focusable containers inside a clipping parent use `insetFocusRing` (`lib/cx`) so the focus ring is not cut off.

## 8. RTL readiness

Full RTL support is not implemented. The primitives use flex/grid with `gap` and no physical left/right margins or offsets, so they mirror under `dir="rtl"`. New layout code should prefer logical utilities (`ms-*`, `me-*`, `ps-*`, `pe-*`, `start-*`, `text-start`) where a direction is needed.

## 9. Accessibility

Layout never changes meaning or order. The DOM order is the reading and focus order. `SplitLayout` reorders the DOM rather than using CSS `order`. The only visual reversal is the established mobile action order (primary on top) in `ActionBar`/`PageHeader`. `Section` names its region by its heading. Touch targets stay 44px on mobile (component tokens). T00-10 (Accessibility Foundation) builds on this.

## 10. Verification (T00-09)

- Unit tests (Vitest + axe) cover every primitive and shell change.
- Headless Chromium on the production image: 675/675 checks. These include the complete T00-08 shell regression; `/design-system` and `/design-system/layout` in Light and Dark at 390/640/768/1024/1280/1440; element-level spill checks on every experience; breakpoint edges (767/768, 1023/1024, 1439/1440); layout geometry per width; 44px targets; FilterBar drawer; the table scroll region; keyboard focus order and an unclipped focus ring; reduced motion; System theme; axe 0 violations (no exclusions); no console or hydration errors; no external requests; and `/design-system/layout` returning 404 in production.
