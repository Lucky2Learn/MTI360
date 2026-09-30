import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect } from "vitest";

// WCAG 2.2 contrast helpers for tests (T00-10A). Parses the token CSS that
// ships (tokens/primitives.css, tokens/semantic.css), so token contract tests
// and component tests measure the same values. jsdom cannot compute styles:
// component tests map rendered semantic utility classes to their tokens and
// measure those (docs/architecture/accessibility.md §10, §13).

const TOKENS = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../tokens",
);

export const readTokenFile = (file: string): string =>
  readFileSync(path.join(TOKENS, file), "utf8");

// --- Parsing -------------------------------------------------------------------

type Mix = { a: string; b: string; t: number };
export type Primitive = { hex: string; mix?: Mix };
export type ThemeTokens = Map<string, string>;

function parsePrimitives(css: string): Map<string, Primitive> {
  const result = new Map<string, Primitive>();
  const pattern =
    /--([a-z0-9-]+):\s*(#[0-9a-f]{6});(?:\s*\/\*\s*mix\(([a-z0-9-]+),\s*([a-z0-9-]+),\s*([0-9.]+)\)\s*\*\/)?/gi;
  for (const match of css.matchAll(pattern)) {
    const [, name, hex, a, b, t] = match;
    result.set(name!, {
      hex: hex!.toLowerCase(),
      mix: a && b && t ? { a, b, t: Number(t) } : undefined,
    });
  }
  return result;
}

/** Returns the body of the first `{ … }` block whose selector starts at `marker`. */
export function blockAfter(css: string, marker: string): string {
  const start = css.indexOf(marker);
  if (start === -1) throw new Error(`Block not found: ${marker}`);
  const open = css.indexOf("{", start);
  let depth = 0;
  for (let i = open; i < css.length; i += 1) {
    if (css[i] === "{") depth += 1;
    if (css[i] === "}") depth -= 1;
    if (depth === 0) return css.slice(open + 1, i);
  }
  throw new Error(`Unterminated block: ${marker}`);
}

export function declarations(block: string): ThemeTokens {
  const result: ThemeTokens = new Map();
  const withoutComments = block.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const match of withoutComments.matchAll(
    /--([a-z0-9-]+):\s*([^;]+);/gi,
  )) {
    result.set(match[1]!, match[2]!.trim().replace(/\s+/g, " "));
  }
  return result;
}

const semanticCss = readTokenFile("semantic.css");

export const primitives = parsePrimitives(readTokenFile("primitives.css"));
export const light = declarations(
  blockAfter(semanticCss, ':root,\n[data-theme="light"]'),
);
export const dark = declarations(
  blockAfter(semanticCss, '[data-theme="dark"] {'),
);
/** The no-JavaScript prefers-color-scheme: dark fallback (System without JS). */
export const fallback = declarations(
  blockAfter(
    blockAfter(semanticCss, "@media (prefers-color-scheme: dark)"),
    ":root:not([data-theme])",
  ),
);

export const THEMES: [string, ThemeTokens][] = [
  ["Light", light],
  ["Dark", dark],
];

// --- Colour maths (WCAG 2.2) ------------------------------------------------------

function channels(hex: string): [number, number, number] {
  const value = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16)) as [
    number,
    number,
    number,
  ];
}

/** mix(a, b, t) = per sRGB channel round(t × a + (1 − t) × b). */
export function mix(a: string, b: string, t: number): string {
  const ca = channels(a);
  const cb = channels(b);
  return `#${ca
    .map((c, i) => Math.round(c * t + cb[i]! * (1 - t)))
    .map((c) => c.toString(16).padStart(2, "0"))
    .join("")}`;
}

function luminance(hex: string): number {
  const [r, g, b] = channels(hex).map((c) => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [
    number,
    number,
  ];
  return (hi + 0.05) / (lo + 0.05);
}

/** Resolves a semantic colour token to its primitive hex value. */
export function resolve(theme: ThemeTokens, token: string): string {
  const value = theme.get(token);
  const reference = value?.match(/^var\(--([a-z0-9-]+)\)$/)?.[1];
  const primitive = reference ? primitives.get(reference) : undefined;
  if (!primitive) throw new Error(`Cannot resolve --${token} (${value})`);
  return primitive.hex;
}

/**
 * Reusable WCAG 2.2 contrast assertion: resolves both semantic tokens in the
 * given theme and reports the pair, the colours and the measured ratio on
 * failure. Returns the ratio.
 */
export function expectContrast(
  theme: ThemeTokens,
  foreground: string,
  background: string,
  minimum: number,
): number {
  const fg = resolve(theme, foreground);
  const bg = resolve(theme, background);
  const ratio = contrast(fg, bg);
  expect(
    ratio,
    `${foreground} ${fg} on ${background} ${bg} = ${ratio.toFixed(2)}:1`,
  ).toBeGreaterThanOrEqual(minimum);
  return ratio;
}
