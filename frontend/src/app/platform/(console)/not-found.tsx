import { ShellNotFound } from "@/shells";

import type { Metadata } from "next";

// The platform console's not-found view (T01-09B), inside the shell: one
// answer for an unknown path and an UNRELEASED page outside development.
export const metadata: Metadata = {
  title: "Not found · Platform Administration · MTI 360",
};

export default function PlatformNotFound() {
  return <ShellNotFound homeHref="/platform" homeLabel="Go to overview" />;
}
