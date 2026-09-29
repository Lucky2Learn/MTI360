import { describe, expect, it } from "vitest";

import {
  gapClasses,
  gridColumnClasses,
  gridSpanClasses,
  responsiveClasses,
  type Breakpoint,
} from "./responsive";

const PREFIX: Record<Breakpoint, string> = {
  base: "",
  tablet: "tablet:",
  desktop: "desktop:",
  large: "large:",
};

describe("responsiveClasses", () => {
  it("uses the base classes for a single value", () => {
    expect(responsiveClasses(3, gridColumnClasses)).toBe("grid-cols-3");
  });

  it("emits one class per breakpoint that is set, in mobile-first order", () => {
    expect(
      responsiveClasses(
        { large: 4, base: 1, desktop: 3, tablet: 2 },
        gridColumnClasses,
      ),
    ).toBe(
      "grid-cols-1 tablet:grid-cols-2 desktop:grid-cols-3 large:grid-cols-4",
    );
    expect(responsiveClasses({ desktop: 2 }, gridColumnClasses)).toBe(
      "desktop:grid-cols-2",
    );
    expect(responsiveClasses({}, gridColumnClasses)).toBe("");
  });
});

describe("responsive class maps", () => {
  it("only use the approved breakpoint prefixes", () => {
    for (const tier of Object.keys(PREFIX) as Breakpoint[]) {
      for (const value of [
        ...Object.values(gridColumnClasses[tier]),
        ...Object.values(gridSpanClasses[tier]),
      ]) {
        expect(value.startsWith(PREFIX[tier])).toBe(true);
        expect(value.slice(PREFIX[tier].length)).toMatch(
          /^(grid-cols|col-span)-(\d+|full)$/,
        );
      }
    }
  });

  it("maps each column count and span to the matching utility", () => {
    expect(gridColumnClasses.desktop[12]).toBe("desktop:grid-cols-12");
    expect(gridSpanClasses.tablet[7]).toBe("tablet:col-span-7");
    expect(gridSpanClasses.large.full).toBe("large:col-span-full");
  });

  it("keeps spacing on the 4px scale of DESIGN-SYSTEM.md §20", () => {
    const steps = Object.values(gapClasses)
      .flatMap((classes) => classes.split(" "))
      .map((utility) => Number(utility.replace(/^(tablet:)?gap-/, "")));
    for (const step of steps) expect([0, 1, 2, 3, 4, 6, 8, 12]).toContain(step);
  });

  it("grows only the section-level gaps from tablet", () => {
    expect(gapClasses.md).toBe("gap-4");
    expect(gapClasses.xl).toBe("gap-6 tablet:gap-8");
    expect(gapClasses["2xl"]).toBe("gap-8 tablet:gap-12");
  });
});
