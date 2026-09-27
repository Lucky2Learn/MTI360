# design-system/

Shared visual foundation for all four experiences. Values come from [DESIGN-SYSTEM.md](../../../DESIGN-SYSTEM.md); architecture and catalogue: [docs/architecture/design-tokens.md](../../../docs/architecture/design-tokens.md); decision: [ADR-0007](../../../docs/adr/0007-styling-tailwind-semantic-tokens.md).

| Directory | Contents | Task |
|---|---|---|
| `tokens/` | `primitives.css` (palette + derived; the only raw colours), `semantic.css` (Light / Dark mappings), `tailwind.css` (Tailwind v4 `@theme`), token and guard tests | T00-06 |
| `theme/` | Light / Dark / System preference, pre-paint script, `ThemeProvider` / `useTheme`, `ThemeSelector` | T00-06 |
| `typography/` | Self-hosted Inter (`next/font/local`) | T00-06 |
| `components/` | Core components | T00-07 |
| `templates/` | Page templates T01–T18 | later |

## Rules

- Style with semantic utilities only: `bg-surface-primary`, `text-text-secondary`, `border-border-default`, `text-page-title`, `rounded-md`, `shadow-sm`, `p-4`, `tablet:` / `desktop:` / `large:`.
- No raw colours (hex, `rgb()`, `hsl()`, …) outside `tokens/primitives.css` and no `dark:` utilities — both fail `tokens/guard.test.ts`.
- No arbitrary values (`p-[17px]`, `bg-[…]`) and no off-grid spacing (`p-7`); add a token instead.
- Text uses `text-*`, `link` or `*-text` tokens (≥ 4.5:1). `accent-maritime`, `accent-brass` and state colours (`success`, …) are for non-text indicators.
- Never communicate status by colour alone.
- `design-system/` imports nothing from `features/`.
