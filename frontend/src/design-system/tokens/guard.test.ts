import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// Token guard (T00-06, DESIGN-SYSTEM.md §78 and §80):
// 1. Raw colour values may appear only in the primitive layer (primitives.css).
// 2. The Tailwind dark: variant is not used; theme changes go through semantic
//    tokens. Only design-system/tokens/ may define it.

// Paths come from node:path (Vite rewrites directory `new URL(…, import.meta.url)`).
const SELF = fileURLToPath(import.meta.url);
const TOKENS = path.dirname(SELF);
const SRC = path.resolve(TOKENS, "../..");
const PRIMITIVES = path.join(TOKENS, "primitives.css");

const RAW_COLOUR =
  /#(?:[0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{3,4})\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(/i;
const DARK_VARIANT = /(?:^|[\s"'`{(])dark:[a-z[-]/;

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(full);
    return /\.(?:css|ts|tsx|mts|js|jsx|mjs)$/.test(entry.name) ? [full] : [];
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

const files = sourceFiles(SRC).filter((file) => file !== SELF);

describe("design-token guard", () => {
  it("finds the frontend source files", () => {
    expect(files.length).toBeGreaterThan(5);
    expect(files).toContain(PRIMITIVES);
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
});
