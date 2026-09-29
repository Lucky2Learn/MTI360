// MTI 360 responsive layout primitives (T00-09). Screens import layout from
// "@/design-system/layout". Conventions: docs/architecture/layout.md
// Page structure (PageContainer, PageHeader, PageContent) belongs to the
// application shell ("@/shells") and composes these primitives.

export * from "./ActionBar";
export * from "./Container";
export * from "./Grid";
export * from "./Inline";
export * from "./Section";
export * from "./Show";
export * from "./SplitLayout";
export * from "./Stack";
export type {
  Breakpoint,
  CrossAlign,
  Gap,
  GridColumns,
  GridSpan,
  Justify,
  Responsive,
  StackBelow,
} from "./responsive";
