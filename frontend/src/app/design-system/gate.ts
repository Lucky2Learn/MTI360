// Showcase gate (T00-07, decision D8). The component showcase exists only in
// development and test. Any other environment — or any configuration error —
// disables it (fail closed). It contains no data, but it is not a product page.

export const SHOWCASE_ENVIRONMENTS = ["development", "test"] as const;

export function isShowcaseEnabled(appEnv: string | undefined): boolean {
  return (SHOWCASE_ENVIRONMENTS as readonly string[]).includes(appEnv ?? "");
}
