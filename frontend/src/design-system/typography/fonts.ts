import localFont from "next/font/local";

// Inter variable font (DESIGN-SYSTEM.md §17), self-hosted from the pinned
// @fontsource-variable/inter package (T00-06, decision D3): no request to a
// font CDN at build time or run time. next/font emits the files as static
// assets, preloads the Latin subset and generates a metric-adjusted fallback.
//
// Two subsets with the fontsource unicode ranges. The Latin Extended face is
// only downloaded when such characters appear (for example ₹ U+20B9 and
// accented names). Both CSS variables feed --font-sans (tokens/tailwind.css).

// next/font requires literal arguments, so the file paths are written out.

export const interLatin = localFont({
  src: "../../../node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
  weight: "100 900",
  style: "normal",
  display: "swap",
  variable: "--font-inter-latin",
  declarations: [
    {
      prop: "unicode-range",
      value:
        "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
    },
  ],
});

export const interLatinExt = localFont({
  src: "../../../node_modules/@fontsource-variable/inter/files/inter-latin-ext-wght-normal.woff2",
  weight: "100 900",
  style: "normal",
  display: "swap",
  preload: false,
  variable: "--font-inter-latin-ext",
  declarations: [
    {
      prop: "unicode-range",
      value:
        "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF",
    },
  ],
});

/** Class names that define both font CSS variables; apply on <html>. */
export const fontVariables = `${interLatin.variable} ${interLatinExt.variable}`;
