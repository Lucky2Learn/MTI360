# ADR-0007 — Styling: Tailwind CSS v4 with Semantic Design Tokens

- **Status:** Accepted
- **Date:** 2026-09-27
- **Task:** T00-06
- **Related:** ADR-0001 (styling "approved in principle; confirmed in T00-06/T00-07"); DESIGN-SYSTEM.md §10–§16, §76–§80; CLAUDE.md §16–§23; [docs/architecture/design-tokens.md](../architecture/design-tokens.md)

## Context

ADR-0001 approved "Tailwind CSS mapped to semantic design tokens" in principle and deferred confirmation to T00-06/T00-07. MTI 360 needs one styling foundation for four experiences that:

- consumes DESIGN-SYSTEM.md values only (no arbitrary colours, sizes, radii — CLAUDE.md §20);
- supports Light, Dark and System themes as designed mappings, not inversion (§16);
- lets components switch theme without per-component dark-mode code (DESIGN-SYSTEM.md §80);
- stays fast to build with and consistent across ~222 screens (CLAUDE.md §24).

## Decision

1. **Tailwind CSS 4.3.3** (CSS-first configuration, `@tailwindcss/postcss`) is the styling system of the frontend.
2. **Three token layers** in `frontend/src/design-system/tokens/`: primitives (raw values, the only place for raw colours) → semantic tokens with separate Light and Dark mappings (CSS custom properties switched by `data-theme` on `<html>`) → Tailwind `@theme` mapping. Components use semantic utilities only.
3. **Tailwind defaults are removed** for colours, font families, type sizes, font weights, radii, shadows and breakpoints; only MTI 360 tokens are available as utilities.
4. The `dark:` variant is defined to follow `data-theme` but is **not used** by components; theme differences live in the semantic mapping.
5. **Fonts:** Inter variable, self-hosted from `@fontsource-variable/inter` via `next/font/local`; monospace uses the system stack (no additional font — closes INC-12 for the application).
6. Where a DESIGN-SYSTEM.md colour fails WCAG 2.2 AA for text, the specification value is kept for non-text use and a **documented derived mix of palette colours** is used for text (INC-17). DESIGN-SYSTEM.md is not modified.
7. **Headless component primitives** (e.g. Radix) remain an ADR-0001 item to be confirmed in T00-07.

## Consequences

- Theme switching is a single attribute change; components carry no theme logic.
- Arbitrary colour values are blocked by a test (only `primitives.css` may contain raw colours; no `dark:` outside the token layer). Arbitrary spacing and size values remain technically possible in Tailwind and are controlled by review.
- New visual values require a token change (and, for new colours, a DESIGN-SYSTEM.md update), keeping the design system authoritative.
- The build depends on Tailwind's native components (`@tailwindcss/oxide`, `lightningcss`) delivered as platform packages without install scripts.
- The inline pre-paint theme script must receive the CSP nonce once a Content-Security-Policy is introduced.

## Alternatives considered

- **CSS Modules / plain CSS with custom properties only** — no utility layer; every component would re-declare layout and spacing rules, increasing drift across ~222 screens. Rejected.
- **CSS-in-JS (runtime)** — runtime cost and friction with React Server Components. Rejected.
- **Keep Tailwind's default palette alongside tokens** — makes non-MTI 360 colours one class away (`bg-blue-500`). Rejected.
- **`next/font/google`** — downloads fonts from Google at build time (network dependency in CI and Docker builds). Rejected in favour of the pinned, self-hosted package.
- **CSS `light-dark()` for the theme mapping** — less duplication, but depends on build-time polyfilling for older browsers and does not cover non-colour values. Rejected for explicit `data-theme` blocks.
