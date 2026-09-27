import axe from "axe-core";
import { expect } from "vitest";

// Automated accessibility check for component tests (T00-07, decision D7).
//
// Runs axe-core on a rendered container. Two rules are disabled in jsdom only:
// - color-contrast: jsdom cannot compute styles; contrast is verified by the
//   token contrast tests and by axe in real Chromium (browser verification);
// - region: isolated components are not placed inside page landmarks; landmark
//   structure belongs to the shell and pages (T00-08, T00-10).
export async function expectNoA11yViolations(
  container: Element,
): Promise<void> {
  const results = await axe.run(container, {
    resultTypes: ["violations"],
    rules: {
      "color-contrast": { enabled: false },
      region: { enabled: false },
    },
  });
  expect(
    results.violations.map(
      (violation) =>
        `${violation.id}: ${violation.nodes.map((node) => node.target.join(" ")).join(", ")}`,
    ),
  ).toEqual([]);
}
