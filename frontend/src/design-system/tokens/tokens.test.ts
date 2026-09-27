import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// Design-token contract (T00-06; interaction states and component tokens T00-07). Parses the token CSS directly, so the files
// that ship are the files that are tested.

const HERE = path.dirname(fileURLToPath(import.meta.url));
const read = (relative: string): string =>
  readFileSync(path.resolve(HERE, relative), "utf8");

const primitivesCss = read("./primitives.css");
const semanticCss = read("./semantic.css");
const tailwindCss = read("./tailwind.css");
const componentsCss = read("./components.css");
const designSystemMd = read("../../../../DESIGN-SYSTEM.md");

// --- Parsing helpers ---------------------------------------------------------

type Mix = { a: string; b: string; t: number };
type Primitive = { hex: string; mix?: Mix };

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
function blockAfter(css: string, marker: string): string {
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

function declarations(block: string): Map<string, string> {
  const result = new Map<string, string>();
  const withoutComments = block.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const match of withoutComments.matchAll(
    /--([a-z0-9-]+):\s*([^;]+);/gi,
  )) {
    result.set(match[1]!, match[2]!.trim().replace(/\s+/g, " "));
  }
  return result;
}

const primitives = parsePrimitives(primitivesCss);
const light = declarations(
  blockAfter(semanticCss, ':root,\n[data-theme="light"]'),
);
const dark = declarations(blockAfter(semanticCss, '[data-theme="dark"] {'));
const fallback = declarations(
  blockAfter(
    blockAfter(semanticCss, "@media (prefers-color-scheme: dark)"),
    ":root:not([data-theme])",
  ),
);

// --- Colour maths (WCAG 2.2) ----------------------------------------------------

function channels(hex: string): [number, number, number] {
  const value = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16)) as [
    number,
    number,
    number,
  ];
}

function mix(a: string, b: string, t: number): string {
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

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [
    number,
    number,
  ];
  return (hi + 0.05) / (lo + 0.05);
}

/** Resolves a semantic colour token to its primitive hex value. */
function resolve(theme: Map<string, string>, token: string): string {
  const value = theme.get(token);
  const reference = value?.match(/^var\(--([a-z0-9-]+)\)$/)?.[1];
  const primitive = reference ? primitives.get(reference) : undefined;
  if (!primitive) throw new Error(`Cannot resolve --${token} (${value})`);
  return primitive.hex;
}

// --- Contract ---------------------------------------------------------------------

const DESIGN_SYSTEM_SEMANTIC_TOKENS = [
  "background-primary",
  "background-secondary",
  "surface-primary",
  "surface-secondary",
  "surface-elevated",
  "text-primary",
  "text-secondary",
  "text-muted",
  "text-inverse",
  "border-subtle",
  "border-default",
  "border-strong",
  "brand-primary",
  "brand-secondary",
  "accent-maritime",
  "accent-brass",
  "success",
  "warning",
  "error",
  "info",
  "ai-primary",
  "ai-surface",
  "ai-border",
];

const BACKGROUNDS = [
  "background-primary",
  "background-secondary",
  "surface-primary",
  "surface-secondary",
  "surface-elevated",
];
const STATES = ["success", "warning", "error", "info"];

/** [foreground, background, minimum ratio] — 4.5:1 text, 3:1 non-text (WCAG 2.2 AA). */
const CONTRAST_PAIRS: [string, string, number][] = [
  ...["text-primary", "text-secondary", "text-muted", "link"].flatMap((text) =>
    BACKGROUNDS.map((bg): [string, string, number] => [text, bg, 4.5]),
  ),
  ["text-inverse", "brand-primary", 4.5],
  ...STATES.flatMap((state): [string, string, number][] => [
    [`${state}-text`, `${state}-surface`, 4.5],
    [`${state}-text`, "surface-primary", 4.5],
    [`${state}-text`, "background-primary", 4.5],
    [state, `${state}-surface`, 3],
    [state, "surface-primary", 3],
  ]),
  ["ai-primary", "ai-surface", 4.5],
  ["ai-primary", "surface-primary", 4.5],
  ...["border-strong", "focus-ring", "accent-maritime"].flatMap((ui) =>
    BACKGROUNDS.map((bg): [string, string, number] => [ui, bg, 3]),
  ),
  // Interaction states (T00-07)
  ...["surface-hover", "surface-selected"].flatMap(
    (bg): [string, string, number][] => [
      ["text-primary", bg, 4.5],
      ["text-secondary", bg, 4.5],
      ["focus-ring", bg, 3],
    ],
  ),
  ...["brand-primary-hover", "success-strong", "error-strong"].map(
    (bg): [string, string, number] => ["text-inverse", bg, 4.5],
  ),
];

describe("primitive tokens", () => {
  it("contain every DESIGN-SYSTEM.md §6–§8 colour verbatim", () => {
    const start = designSystemMd.indexOf("# 6. COLOR SYSTEM");
    const end = designSystemMd.indexOf("# 9. COLOR RATIO");
    const specColours = new Set(
      [...designSystemMd.slice(start, end).matchAll(/#[0-9A-Fa-f]{6}\b/g)].map(
        (m) => m[0].toLowerCase(),
      ),
    );
    const paletteValues = new Set(
      [...primitives.values()].filter((p) => !p.mix).map((p) => p.hex),
    );

    expect(specColours.size).toBe(29);
    for (const colour of specColours) {
      expect(paletteValues, `missing ${colour}`).toContain(colour);
    }
    // No palette colour outside the specification (white is named in §11.1).
    const allowed = [...specColours, primitives.get("white")!.hex];
    for (const colour of paletteValues) {
      expect(allowed, `unexpected ${colour}`).toContain(colour);
    }
  });

  it("derive every non-palette colour exactly from two palette colours", () => {
    const derived = [...primitives].filter(([, p]) => p.mix);
    expect(derived.length).toBeGreaterThan(0);
    for (const [name, { hex, mix: m }] of derived) {
      const a = primitives.get(m!.a);
      const b = primitives.get(m!.b);
      expect(
        a?.mix,
        `${name}: ${m!.a} must be a palette colour`,
      ).toBeUndefined();
      expect(
        b?.mix,
        `${name}: ${m!.b} must be a palette colour`,
      ).toBeUndefined();
      expect(hex, name).toBe(mix(a!.hex, b!.hex, m!.t));
    }
  });
});

describe("semantic tokens", () => {
  it("define every DESIGN-SYSTEM.md §10 token", () => {
    for (const token of DESIGN_SYSTEM_SEMANTIC_TOKENS) {
      expect(light.has(token), token).toBe(true);
    }
  });

  it("have both a Light and a Dark mapping for every token", () => {
    expect([...dark.keys()].sort()).toEqual([...light.keys()].sort());
  });

  it("keep the no-JavaScript fallback identical to the Dark mapping", () => {
    expect(Object.fromEntries(fallback)).toEqual(Object.fromEntries(dark));
  });

  it("reference primitives only (no raw colour values)", () => {
    for (const theme of [light, dark]) {
      for (const [token, value] of theme) {
        expect(value, token).not.toMatch(/#|rgba?\(|hsla?\(|oklch\(|oklab\(/i);
        const references = [...value.matchAll(/var\(--([a-z0-9-]+)\)/g)].map(
          (m) => m[1]!,
        );
        expect(references.length, token).toBeGreaterThan(0);
        for (const reference of references) {
          expect(primitives.has(reference), `${token} → ${reference}`).toBe(
            true,
          );
        }
      }
    }
  });

  it("are all exposed through the Tailwind theme and nothing else is", () => {
    const colourTokens = [...light.keys()].filter(
      (token) => !token.startsWith("elevation-"),
    );
    const mapped = [
      ...tailwindCss.matchAll(/--color-([a-z0-9-]+):\s*([^;]+);/g),
    ];
    expect(mapped.map((m) => m[1]).sort()).toEqual(colourTokens.sort());
    for (const [, name, value] of mapped) {
      expect(value).toBe(`var(--${name})`);
    }
  });

  it("component tokens reference semantic tokens only", () => {
    const references = [
      ...componentsCss.matchAll(/var\(--([a-z0-9-]+)\)/g),
    ].map((m) => m[1]!);
    for (const reference of references) {
      expect(primitives.has(reference), `${reference} is a primitive`).toBe(
        false,
      );
      expect(
        light.has(reference) || /^(control|focus-ring|z)-/.test(reference),
        reference,
      ).toBe(true);
    }
    for (const size of ["sm", "md", "lg"]) {
      expect(tailwindCss).toContain(
        `--spacing-control-${size}: var(--control-height-${size});`,
      );
    }
  });

  it("remove Tailwind default colours, type sizes, radii, shadows and breakpoints", () => {
    for (const namespace of [
      "color",
      "font",
      "text",
      "font-weight",
      "radius",
      "shadow",
      "breakpoint",
    ]) {
      expect(tailwindCss).toContain(`--${namespace}-*: initial;`);
    }
  });
});

describe.each([
  ["Light", light],
  ["Dark", dark],
])("WCAG 2.2 AA contrast — %s theme", (_theme, mapping) => {
  it.each(CONTRAST_PAIRS)(
    "%s on %s ≥ %s:1",
    (foreground, background, minimum) => {
      const ratio = contrast(
        resolve(mapping, foreground),
        resolve(mapping, background),
      );
      expect(ratio).toBeGreaterThanOrEqual(minimum);
    },
  );
});
