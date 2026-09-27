# Design Tokens

- **Status:** Implemented in T00-06 (2026-09-27)
- **Decision basis:** [DESIGN-SYSTEM.md](../../DESIGN-SYSTEM.md) (source of truth for values), [ADR-0007](../adr/0007-styling-tailwind-semantic-tokens.md) (Tailwind CSS v4 + semantic tokens), T00-06 decisions D1–D10
- **Code:** `frontend/src/design-system/tokens/`, `frontend/src/design-system/theme/`, `frontend/src/design-system/typography/fonts.ts`
- **Related:** [repository-structure.md](repository-structure.md), [toolchain.md](toolchain.md), [spec-inconsistencies.md](spec-inconsistencies.md) (INC-12, INC-13, INC-17)

## 1. Architecture

```text
primitives.css   palette verbatim from DESIGN-SYSTEM.md §6–§8 + documented derived mixes
      ↓          (the ONLY file with raw colour values)
semantic.css     DESIGN-SYSTEM.md §10 names, one Light and one Dark mapping,
      ↓          + no-JS prefers-color-scheme fallback (identical to Dark)
tailwind.css     Tailwind v4 @theme: defaults removed, semantic tokens → utilities
      ↓
components       T00-07 onwards: utilities only (bg-surface-primary, text-text-secondary, …)
```

- Components **never** use primitives or raw values, and **never** branch on the theme (no `dark:` utilities, DESIGN-SYSTEM.md §80). A theme switch only changes `data-theme` on `<html>`; the semantic variables do the rest, with no reload (§15).
- Tailwind's default colours, font families, type sizes, font weights, radii, shadows and breakpoints are removed (`--x-*: initial`). Only MTI 360 values exist as utilities.
- Component tokens (for example `button-primary-background`) are defined with the components in T00-07, on top of the semantic layer.

## 2. Primitive colours

All 29 colours of DESIGN-SYSTEM.md §6–§8 are copied verbatim (a test compares them with the specification), plus `white` (§11.1 Light surface).

| Family | Tokens |
|---|---|
| Deep Ocean | `ocean-900` #06283D · `ocean-800` #073B57 · `ocean-700` #0A4F6E |
| Midnight | `midnight-950` #04151F · `midnight-900` #071E2B · `midnight-800` #0B2A3A |
| Sea Glass | `seaglass-700` #168F91 · `seaglass-600` #1CA7A5 · `seaglass-500` #4CB9B4 · `seaglass-100` #DDF4F2 |
| Pearl | `pearl-50` #F8FAF9 · `pearl-100` #F1F5F4 · `pearl-200` #E5ECEA |
| Ice | `ice-50` #F5FAFC · `ice-100` #EAF4F7 · `ice-200` #D9E9EE |
| Brass | `brass-600` #B88A44 · `brass-500` #C69B5A · `brass-100` #F5EBDD |
| States (§7) | `success-600/100` #21875A/#E5F4EC · `warning-600/100` #B7791F/#FFF4DD · `error-600/100` #C44545/#FDECEC · `info-600/100` #2774A6/#E7F2FA |
| AI (§8) | `ai-600` #7056A8 · `ai-100` #F0ECF8 |

### Derived colours (decision D4)

The palette has no mid-neutrals, and several specification colours fail WCAG 2.2 AA when used as **text** (INC-17). Derived colours are **mixes of two palette colours**, with no new hues:

`mix(a, b, t)` = per sRGB channel `round(t × a + (1 − t) × b)` (round half up). Each derived token carries its formula as a comment in `primitives.css`; a test recomputes every one.

| Purpose | Tokens (formula) |
|---|---|
| Light neutrals | `ink-700` = mix(ocean-900, pearl-50, 0.8) · `ink-600` = 0.66 · `ink-400` = 0.52 |
| Dark neutrals ("muted Ice") | `mist-300` = mix(ice-100, midnight-900, 0.84) · `mist-400` = 0.68 · `mist-600` = 0.52 · `mist-800` = 0.14 · `mist-850` = 0.24 |
| Light text variants | `seaglass-800` = mix(seaglass-700, ocean-900, 0.75) · `success-700` = mix(success-600, ocean-900, 0.85) · `warning-700` = 0.75 · `error-700` = 0.88 · `info-700` = 0.88 · `ai-300` = mix(ai-600, ai-100, 0.4) |
| Dark state and AI colours | `success-400` = mix(success-600, ice-100, 0.7) · `warning-400` = 0.8 · `error-400` = 0.7 · `info-400` = 0.68 · `ai-400` = 0.58 |
| Dark state and AI surfaces | `success-950` = mix(success-600, midnight-900, 0.18) · `warning-950` = 0.16 · `error-950` = 0.18 · `info-950` = 0.2 · `ai-950` = 0.2 · `ai-800` = 0.45 |

## 3. Semantic tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `background-primary` | pearl-50 | midnight-950 | Page background |
| `background-secondary` | ice-50 | midnight-900 | Secondary page areas |
| `surface-primary` | white | midnight-800 | Cards, panels |
| `surface-secondary` | pearl-100 | ocean-900 | Nested / subtle surfaces |
| `surface-elevated` | white | ocean-800 | Menus, dialogs, drawers |
| `text-primary` | ocean-900 | pearl-50 | Body and headings |
| `text-secondary` | ink-700 | mist-300 | Supporting text |
| `text-muted` | ink-600 | mist-400 | Captions, metadata (still ≥ 4.5:1) |
| `text-inverse` | pearl-50 | midnight-950 | Text on `brand-primary` |
| `link` | seaglass-800 | seaglass-500 | Links and text-level interaction |
| `border-subtle` | pearl-200 | mist-800 | Dividers (decorative) |
| `border-default` | ice-200 | mist-850 | Card and control outlines (decorative) |
| `border-strong` | ink-400 | mist-600 | Boundaries that must be perceivable (≥ 3:1) |
| `focus-ring` | seaglass-700 | seaglass-500 | Visible focus (≥ 3:1) |
| `brand-primary` | ocean-800 | seaglass-500 | Primary brand / action surface |
| `brand-secondary` | ocean-700 | ocean-700 | Secondary brand surface |
| `accent-maritime` | seaglass-700 | seaglass-500 | Non-text interaction accents, indicators |
| `accent-brass` | brass-600 | brass-500 | Premium accent, sparingly, non-text |
| `success` / `warning` / `error` / `info` | spec primaries | derived *-400 | Icons and indicators (non-text, ≥ 3:1) |
| `*-surface` | spec surfaces | derived *-950 | State backgrounds |
| `*-text` | derived *-700 | derived *-400 | State text (≥ 4.5:1) |
| `ai-primary` / `ai-surface` / `ai-border` | ai-600 / ai-100 / ai-300 | ai-400 / ai-950 / ai-800 | AI components, restrained |
| `elevation-sm/md/lg` | Deep Ocean shadows 6% / 8% / 12% | Midnight 30% / 35% / 45% (near-invisible) | `shadow-sm/md/lg` |

Status is never communicated by colour alone (§7): pair `*-text`/`*` with an icon, label or shape.

## 4. Non-colour tokens (Tailwind utilities)

| Scale | Values | Utilities |
|---|---|---|
| Font family | Inter variable (self-hosted, D3); system monospace (D6) | `font-sans`, `font-mono` |
| Type (§18) | display 48/56 700 · page-title 32/40 700 · section 24/32 650 · card-heading 18/24 600 · body 16/24 · body-sm 14/20 · caption 13/18 · caption-sm 12/16 | `text-display`, `text-page-title`, `text-section`, `text-card-heading`, `text-body`, `text-body-sm`, `text-caption`, `text-caption-sm` |
| Weight | 400 · 500 · 600 · 650 · 700 | `font-normal`, `font-medium`, `font-semibold`, `font-heading`, `font-bold` |
| Spacing (§20) | 4px unit; use 1 2 3 4 5 6 8 10 12 16 20 24 (= 4 … 96 px) | `p-4`, `gap-6`, … |
| Radius (§34) | 4 · 6 · 8 · 10 · 12 · 16 · 20 · pill | `rounded-xs` … `rounded-3xl`, `rounded-full` |
| Elevation (§35) | theme-dependent (§3) | `shadow-sm`, `shadow-md`, `shadow-lg` |
| Breakpoints (§21, D10) | tablet 768 · desktop 1024 · large 1440 (mobile 390–767 is the base) | `tablet:`, `desktop:`, `large:` |

Body and caption line heights are not specified in §18; they follow the 4px grid. Responsive type sizes (§19), layout, grid and content-width tokens (§79–§83) are T00-09. Motion tokens and component focus styling are T00-10.

**Rules:** do not use arbitrary values (`p-[17px]`, `text-[15px]`, `bg-[…]`) or off-grid spacing steps (`p-7`). Raw colours are rejected by a test; the other rules are enforced in review.

## 5. Contrast (WCAG 2.2 AA)

`tokens.test.ts` resolves every semantic token to its primitive and checks, in **both** themes:

- **4.5:1 (text):** `text-primary`, `text-secondary`, `text-muted`, `link` on all five backgrounds and surfaces; `text-inverse` on `brand-primary`; each `*-text` on its `*-surface`, `surface-primary` and `background-primary`; `ai-primary` on `ai-surface` and `surface-primary`.
- **3:1 (non-text):** `border-strong`, `focus-ring`, `accent-maritime` on all backgrounds and surfaces; each state indicator on its surface and on `surface-primary`.

Selected ratios:

| Pair | Min | Light | Dark |
|---|---|---|---|
| `text-primary` on `background-primary` | 4.5:1 | 14.53 | 17.69 |
| `text-primary` on `surface-primary` | 4.5:1 | 15.23 | 14.24 |
| `text-secondary` on `surface-secondary` | 4.5:1 | 7.51 | 9.86 |
| `text-muted` on `surface-secondary` | 4.5:1 | 4.80 | 6.82 |
| `link` on `surface-secondary` | 4.5:1 | 4.95 | 6.46 |
| `text-inverse` on `brand-primary` | 4.5:1 | 11.30 | 7.87 |
| `success-text` on `success-surface` | 4.5:1 | 4.71 | 4.94 |
| `warning-text` on `warning-surface` | 4.5:1 | 4.82 | 5.06 |
| `error-text` on `error-surface` | 4.5:1 | 5.05 | 4.79 |
| `info-text` on `info-surface` | 4.5:1 | 5.08 | 4.74 |
| `ai-primary` on `ai-surface` | 4.5:1 | 5.04 | 5.44 |
| `border-strong` on `surface-secondary` | 3:1 | 3.14 | 4.44 |
| `focus-ring` on `surface-secondary` | 3:1 | 3.56 | 6.46 |

Specification colours that fail AA as text (kept verbatim for non-text use; INC-17): Sea Glass #168F91 on white 3.91:1 (white text on it also 3.91:1), #1CA7A5 2.95:1; warning #B7791F on its surface 3.33:1; success 3.95:1; error 4.29:1; info 4.47:1; Brass #B88A44 on white 3.11:1.

## 6. Theme (Light / Dark / System)

| Aspect | Implementation |
|---|---|
| Preference | `light` \| `dark` \| `system`, default `system`, `localStorage["mti360.theme"]` (D9). Invalid values → `system`. Per-user persistence for authenticated users: Phase 01 |
| First paint | Inline `<head>` script (`theme/pre-paint.ts`) sets `data-theme` and `color-scheme` before the body renders: no flash. Static constant, allow-listed values, never throws. **Needs the CSP nonce once CSP is introduced** (`src/proxy.ts`) |
| System | Resolved through `prefers-color-scheme`; live changes applied while `system` is selected |
| Cross-tab | `storage` event re-reads the preference |
| No storage | Every access guarded; an in-memory preference keeps the session working |
| No JavaScript | `prefers-color-scheme` CSS fallback (identical to the Dark mapping, tested) |
| React | `ThemeProvider` + `useTheme()` via `useSyncExternalStore` (server snapshot `system`, no hydration mismatch). `suppressHydrationWarning` only on `<html>` |
| Control | `ThemeSelector` (D7): fieldset "Theme" with native radios Light / Dark / System; keyboard operable, 44px targets, selection shown by radio mark, weight and border plus a text description. Placed in the UserMenu by T00-08 (CLAUDE.md §19) |

## 7. Fonts

Inter variable from `@fontsource-variable/inter` 5.3.0 (OFL-1.1) through `next/font/local`: files are emitted as static assets, the Latin subset is preloaded, the Latin Extended subset (including ₹ U+20B9) loads only when needed, and next/font generates metric-adjusted fallbacks. No request goes to a font CDN at build or run time.

## 8. Verification (T00-06)

- Unit tests: palette fidelity, derivations, Light/Dark parity, fallback = Dark, primitives-only references, complete Tailwind mapping and reset, contrast in both themes, guard (raw colours only in `primitives.css`, no `dark:` outside `tokens/`), theme runtime, pre-paint matrix, selector semantics and behaviour.
- Built CSS contains only MTI 360 utilities (no Tailwind default palette, sizes, radii or breakpoints).
- Headless Chromium (production image): Light and Dark at 390 / 768 / 1024 / 1440 without overflow, console warnings or external requests; pre-paint with application JavaScript blocked; no-JS fallback; live System change; keyboard selection with visible focus; cross-tab sync.
