import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// Design-system guard (T00-06, extended in T00-07; DESIGN-SYSTEM.md §78, §80):
// 1. Raw colour values may appear only in the primitive layer (primitives.css).
// 2. The Tailwind dark: variant is not used; theme changes go through semantic
//    tokens. Only design-system/tokens/ may define it.
// 3. No Tailwind arbitrary values (p-[17px], bg-[…], [prop:value]); token
//    references such as outline-(length:--focus-ring-width) and arbitrary
//    variants such as has-[:focus-visible]: remain allowed.
// 4. lucide-react is imported only by design-system/icons/.
// 5. React Aria packages are imported only by design-system/components/.
// 6. dangerouslySetInnerHTML only for the approved pre-paint script (app/layout.tsx).
// 7. (T00-10) outline-none never removes focus without a replacement: a token
//    ring or focus style within the same class statement, or an explicit
//    "a11y-focus:" comment for programmatic focus containers (dialog panels,
//    listbox/menu containers, main#main-content).
// 8. (T00-10) every transition/animation utility is paired with motion-reduce:
//    or motion-safe: on the same line (WCAG 2.3.3; the global CSS net in
//    app/globals.css is only a safety net).
// 9. (T00-10) no positive tabIndex (focus order follows the DOM, WCAG 2.4.3).

// Paths come from node:path (Vite rewrites directory `new URL(…, import.meta.url)`).
const SELF = fileURLToPath(import.meta.url);
const TOKENS = path.dirname(SELF);
const SRC = path.resolve(TOKENS, "../..");
const PRIMITIVES = path.join(TOKENS, "primitives.css");
const ICONS = path.join(SRC, "design-system", "icons");
const COMPONENTS = path.join(SRC, "design-system", "components");
const ROOT_LAYOUT = path.join(SRC, "app", "layout.tsx");

const RAW_COLOUR =
  /#(?:[0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{3,4})\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(/i;
const DARK_VARIANT = /(?:^|[\s"'`{(])dark:[a-z[-]/;
const ARBITRARY_VALUE =
  /(?<![\w-])(?:[a-z0-9-]+:)*-?[a-z][a-z0-9-]*-\[[^\]\s]+\](?!:)|(?<![\w-])\[[a-z-]+:[^\]\s]+\](?![:\w])/;
const LUCIDE_IMPORT = /(?:from\s+|import\s*\(\s*)["']lucide-react["']/;
const REACT_ARIA_IMPORT =
  /(?:from\s+|import\s*\(\s*)["'](?:react-aria-components|react-aria|react-stately|@react-aria\/[^"']+|@react-stately\/[^"']+)["']/;
const RAW_HTML = /dangerouslySetInnerHTML/;
const OUTLINE_NONE = /(?<![\w:-])outline-none(?![\w-])/;
const FOCUS_REPLACEMENT =
  /focusRing|insetFocusRing|fieldFocus|(?:data-focus-visible|focus-visible|data-focused|data-focus-within):|a11y-focus:/;
const MOTION_UTILITY =
  /(?<![\w:-])(?:transition(?:-[a-z]+)?|animate-[a-z]+)(?![\w-])/;
const MOTION_GUARD = /motion-reduce:|motion-safe:/;
const POSITIVE_TABINDEX = /tab[iI]ndex=(?:\{\s*[1-9]|"[1-9])/;

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(full);
    return /\.(?:css|ts|tsx|mts|js|jsx|mjs)$/.test(entry.name) ? [full] : [];
  });
}

/** Lines matching `pattern` with no `allowed` match within `radius` lines. */
function unpairedLines(
  file: string,
  pattern: RegExp,
  allowed: RegExp,
  radius: number,
): string[] {
  const lines = readFileSync(file, "utf8").split(/\r?\n/);
  return lines.flatMap((line, index) => {
    if (!pattern.test(line)) return [];
    const window = lines
      .slice(Math.max(0, index - radius), index + radius + 1)
      .join("\n");
    return allowed.test(window)
      ? []
      : [`${path.relative(SRC, file)}:${index + 1}: ${line.trim()}`];
  });
}

function offendingLines(file: string, pattern: RegExp): string[] {
  return readFileSync(file, "utf8")
    .split(/\r?\n/)
    .flatMap((line, index) =>
      pattern.test(line)
        ? [`${path.relative(SRC, file)}:${index + 1}: ${line.trim()}`]
        : [],
    );
}

const within = (directory: string) => (file: string) =>
  file.startsWith(directory + path.sep);

const files = sourceFiles(SRC).filter((file) => file !== SELF);
const scripts = files.filter((file) =>
  /\.(?:ts|tsx|mts|js|jsx|mjs)$/.test(file),
);

describe("design-system guard", () => {
  it("finds the frontend source files", () => {
    expect(files.length).toBeGreaterThan(5);
    expect(files).toContain(PRIMITIVES);
    expect(files).toContain(ROOT_LAYOUT);
  });

  it("allows raw colour values only in the primitive token layer", () => {
    const offenders = files
      .filter((file) => file !== PRIMITIVES)
      .flatMap((file) => offendingLines(file, RAW_COLOUR));
    expect(offenders).toEqual([]);
  });

  it("does not use the dark: variant outside the token layer", () => {
    const offenders = files
      .filter((file) => !file.startsWith(TOKENS))
      .flatMap((file) => offendingLines(file, DARK_VARIANT));
    expect(offenders).toEqual([]);
  });

  it("does not use Tailwind arbitrary values", () => {
    const offenders = scripts.flatMap((file) =>
      offendingLines(file, ARBITRARY_VALUE),
    );
    expect(offenders).toEqual([]);
  });

  it("imports lucide-react only in design-system/icons", () => {
    const offenders = scripts
      .filter((file) => !within(ICONS)(file))
      .flatMap((file) => offendingLines(file, LUCIDE_IMPORT));
    expect(offenders).toEqual([]);
  });

  it("imports React Aria only in design-system/components", () => {
    const offenders = scripts
      .filter((file) => !within(COMPONENTS)(file))
      .flatMap((file) => offendingLines(file, REACT_ARIA_IMPORT));
    expect(offenders).toEqual([]);
  });

  it("uses dangerouslySetInnerHTML only for the pre-paint script in the root layout", () => {
    const offenders = scripts
      .filter((file) => file !== ROOT_LAYOUT)
      .flatMap((file) => offendingLines(file, RAW_HTML));
    expect(offenders).toEqual([]);
    expect(offendingLines(ROOT_LAYOUT, RAW_HTML)).toHaveLength(1);
  });

  it("never removes the focus outline without a replacement (T00-10)", () => {
    const offenders = scripts
      .filter((file) => !/\.test\.tsx?$/.test(file))
      .flatMap((file) =>
        unpairedLines(file, OUTLINE_NONE, FOCUS_REPLACEMENT, 4),
      );
    expect(offenders).toEqual([]);
  });

  it("pairs every transition and animation with a reduced-motion variant (T00-10)", () => {
    const offenders = scripts
      .filter((file) => !/\.test\.tsx?$/.test(file))
      .flatMap((file) => unpairedLines(file, MOTION_UTILITY, MOTION_GUARD, 0));
    expect(offenders).toEqual([]);
  });

  it("uses no positive tabIndex (T00-10)", () => {
    const offenders = scripts.flatMap((file) =>
      offendingLines(file, POSITIVE_TABINDEX),
    );
    expect(offenders).toEqual([]);
  });
});

// The detectors themselves, so a regex change cannot silently weaken a guard.
describe("guard detectors", () => {
  it.each([
    'className="p-[17px]"',
    'className="bg-[#123456] text-sm"',
    'cx("hover:w-[calc(100%-2rem)]")',
    'className="grid-cols-[1fr_2fr]"',
    'className="-mt-[3px]"',
    'className="[mask-type:luminance]"',
  ])("flags the arbitrary value in %s", (line) => {
    expect(ARBITRARY_VALUE.test(line)).toBe(true);
  });

  it.each([
    'className="has-[:focus-visible]:outline-2 has-checked:font-semibold"',
    'className="data-[state=open]:bg-surface-hover"',
    'className="[&>svg]:size-4"',
    'className="outline-(length:--focus-ring-width) h-control-md"',
    "const pattern = /[a-z0-9-]+/;",
    "type Map = { [key: string]: number };",
  ])("allows %s", (line) => {
    expect(ARBITRARY_VALUE.test(line)).toBe(false);
  });

  it("recognise focus, motion and tab-order patterns (T00-10)", () => {
    expect(OUTLINE_NONE.test('className="rounded outline-none"')).toBe(true);
    expect(OUTLINE_NONE.test('"focus:outline-none"')).toBe(false);
    expect(FOCUS_REPLACEMENT.test("data-focus-visible:outline-solid")).toBe(
      true,
    );
    expect(FOCUS_REPLACEMENT.test("// a11y-focus: dialog panel")).toBe(true);
    expect(FOCUS_REPLACEMENT.test('className="rounded"')).toBe(false);
    expect(MOTION_UTILITY.test('"transition-colors text-body"')).toBe(true);
    expect(MOTION_UTILITY.test('"motion-safe:animate-spin"')).toBe(false);
    expect(MOTION_UTILITY.test('"animate-pulse"')).toBe(true);
    expect(MOTION_GUARD.test("motion-reduce:transition-none")).toBe(true);
    expect(POSITIVE_TABINDEX.test("tabIndex={2}")).toBe(true);
    expect(POSITIVE_TABINDEX.test('tabindex="1"')).toBe(true);
    expect(POSITIVE_TABINDEX.test("tabIndex={0}")).toBe(false);
    expect(POSITIVE_TABINDEX.test("tabIndex={-1}")).toBe(false);
  });

  it("recognises icon, React Aria and raw-HTML usage", () => {
    expect(LUCIDE_IMPORT.test('import { X } from "lucide-react";')).toBe(true);
    expect(
      REACT_ARIA_IMPORT.test('import { Button } from "react-aria-components";'),
    ).toBe(true);
    expect(
      REACT_ARIA_IMPORT.test('import { useFocusRing } from "react-aria";'),
    ).toBe(true);
    expect(
      REACT_ARIA_IMPORT.test('import { useButton } from "@react-aria/button";'),
    ).toBe(true);
    expect(
      REACT_ARIA_IMPORT.test(
        'import { Button } from "@/design-system/components";',
      ),
    ).toBe(false);
    expect(
      RAW_HTML.test("<div dangerouslySetInnerHTML={{ __html: x }} />"),
    ).toBe(true);
  });
});
