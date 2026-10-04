import { ShellNotFound } from "@/shells";

import type { Metadata } from "next";

// RESOURCE-02 (T01-05 UI contract §8.2): the /app not-found view, inside the
// shell. The same view for an unknown path, an UNRELEASED page outside
// development, and a resource the API answers 404 for (missing, another
// institute's, or on a campus outside the member's access).
export const metadata: Metadata = {
  title: "Not found · Tenant Application · MTI 360",
};

export default function TenantNotFound() {
  return <ShellNotFound homeHref="/app" />;
}
