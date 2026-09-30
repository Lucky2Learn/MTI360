import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  dark,
  expectContrast,
  fallback,
  light,
  mix,
  primitives,
} from "@/design-system/testing/contrast";

// Design-token contract (T00-06; interaction states and component tokens T00-07). Parses the token CSS directly, so the files
// that ship are the files that are tested. Parsing and WCAG colour maths live
// in design-system/testing/contrast.ts (T00-10A), shared with component tests.

const HERE = path.dirname(fileURLToPath(import.meta.url));
const read = (relative: string): string =>
  readFileSync(path.resolve(HERE, relative), "utf8");

const tailwindCss = read("./tailwind.css");
const componentsCss = read("./components.css");
const designSystemMd = read("../../../../DESIGN-SYSTEM.md");

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
      expectContrast(mapping, foreground, background, minimum);
    },
  );
});

// T00-10 (docs/architecture/accessibility.md §10).
// brand-primary is the non-text indicator of selected checkboxes, radios and
// switches and the fill of primary buttons: ≥ 3:1 against every surface.
const NON_TEXT_T00_10: [string, string, number][] = [
  ...BACKGROUNDS,
  "surface-hover",
  "surface-selected",
].map((bg): [string, string, number] => ["brand-primary", bg, 3]);

describe.each([
  ["Light", light],
  ["Dark", dark],
])("WCAG 2.2 AA non-text contrast (T00-10) — %s theme", (_theme, mapping) => {
  it.each(NON_TEXT_T00_10)(
    "%s on %s ≥ %s:1",
    (foreground, background, minimum) => {
      expectContrast(mapping, foreground, background, minimum);
    },
  );
});

// State text on every surface it can be rendered on (T00-10, T00-10A):
// page backgrounds, cards, elevated surfaces (dialogs, drawers, popovers,
// menus), hover and selected rows/options, and its own state surface.
const STATE_TEXT_SURFACES = [
  ...BACKGROUNDS,
  "surface-hover",
  "surface-selected",
];
const STATE_TEXT_PAIRS: [string, string][] = STATES.flatMap((state) =>
  [...STATE_TEXT_SURFACES, `${state}-surface`].map((bg): [string, string] => [
    `${state}-text`,
    bg,
  ]),
);

// INC-24 (resolved in T00-10A): Dark *-text used *-400 and measured 3.79–4.22
// on surface-elevated/surface-hover and 4.00–4.45 on surface-selected. Dark
// *-text now maps to the lighter derived *-300 step; every pair must pass.
describe("state text on every surface (T00-10A, INC-24)", () => {
  it.each(STATE_TEXT_PAIRS)("%s on %s ≥ 4.5:1 in Light", (text, bg) => {
    expectContrast(light, text, bg, 4.5);
  });

  it.each(STATE_TEXT_PAIRS)("%s on %s ≥ 4.5:1 in Dark", (text, bg) => {
    expectContrast(dark, text, bg, 4.5);
  });
});

// T00-10A scope: only Dark *-text moved to *-300. Light *-text, and the Dark
// indicators and -strong fills, keep their existing primitives.
describe("state token mappings (T00-10A)", () => {
  it.each(STATES)(
    "%s: Dark text uses %s-300, indicators stay -400",
    (state) => {
      expect(dark.get(`${state}-text`)).toBe(`var(--${state}-300)`);
      expect(dark.get(state)).toBe(`var(--${state}-400)`);
      expect(light.get(`${state}-text`)).toBe(`var(--${state}-700)`);
    },
  );

  it("keeps the success and error -strong fills on -400 in Dark", () => {
    expect(dark.get("success-strong")).toBe("var(--success-400)");
    expect(dark.get("error-strong")).toBe("var(--error-400)");
  });
});
