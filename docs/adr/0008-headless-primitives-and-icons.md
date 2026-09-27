# ADR-0008 — Headless Accessible Primitives (React Aria Components) and Icons (Lucide)

- **Status:** Accepted
- **Date:** 2026-09-27
- **Task:** T00-07 (implemented from T00-07A)
- **Related:** ADR-0001 (styling / primitives row: "headless accessible primitives (e.g. Radix) … confirmed in T00-06/T00-07"); ADR-0007; DESIGN-SYSTEM.md §36, §41–§62; CLAUDE.md §38; [docs/architecture/components.md](../architecture/components.md)

## Context

ADR-0001 approved headless accessible primitives in principle, naming Radix as an example, and deferred the choice to T00-07. ADR-0007 confirmed Tailwind CSS with semantic tokens and left the primitives open. The T00-07 component list includes components with demanding accessibility behaviour: Tabs, Select, **Combobox**, **DatePicker** (keyboard-editable, locale-aware), Modal/Dialog/Drawer (focus management), Toast (live regions) and DataTable. DESIGN-SYSTEM.md §36 requires one coherent icon family, which had not been chosen.

## Decision

1. **React Aria Components** (`react-aria-components`, Adobe, Apache-2.0) is the headless primitive layer. MTI 360 components wrap it and style it only with tokens through Tailwind (React Aria exposes state as `data-*` attributes: `data-hovered`, `data-pressed`, `data-focus-visible`, `data-selected`, `data-disabled`, `data-pending`).
2. **Lucide** (`lucide-react`, ISC) is the single icon family, re-exported under stable names from `design-system/icons`.
3. **Boundaries (enforced by tests):** React Aria packages are imported only inside `design-system/components`; `lucide-react` only inside `design-system/icons`. Screens use `@/design-system/components` and `@/design-system/icons`, so either library can be replaced in one place.
4. `@internationalized/date` (the React Aria date model) is used for the DatePicker (07B), with the locale default `en-IN` and a `locale` prop (INC-20, decision D10).

## Consequences

- One audited dependency covers Combobox, DatePicker, Select, Tabs, overlays and toasts with built-in keyboard models, focus management and internationalized dates; no separate combobox/date/table libraries are needed.
- Interactive components are client components; purely presentational ones (Card, Badge, KPI, Timeline, Alert, Skeleton, EmptyState) stay server-compatible and do not use React Aria.
- Tests use `@testing-library/user-event` because React Aria reacts to realistic pointer and keyboard event sequences.
- React Aria's `Link` performs plain navigation until a `RouterProvider` is configured (application shell, T00-08).
- Some React Aria APIs (historically Toast) may be marked unstable; each is checked when its component is built (07C) and wrapped behind the MTI 360 API.

## Alternatives considered

- **Radix UI** (`radix-ui`, ADR-0001's example) — mature and widely used, but no Combobox, DatePicker or table primitives; T00-07 would need additional libraries (for example cmdk and react-day-picker) with different interaction models and styling hooks. Rejected in favour of a single primitive layer.
- **Custom primitives** — full control, but re-implementing keyboard models, focus management and screen-reader behaviour is high-risk for WCAG 2.2 AA. Rejected.
- **Heroicons / Material Symbols / Phosphor** — viable; Lucide was chosen for its consistent stroke style suiting the restrained maritime design language, broad coverage, tree-shaken per-icon imports and permissive licence.
