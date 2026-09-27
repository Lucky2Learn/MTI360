import { notFound } from "next/navigation";

import { getServerEnv } from "@/lib/env";

import { isShowcaseEnabled } from "./gate";
import { Showcase } from "./showcase";

import type { Metadata } from "next";

// /design-system — component showcase (T00-07, decision D8). Available only when
// APP_ENV is development or test; otherwise 404. Never indexed. Rendered per
// request so the runtime APP_ENV of the container decides, not the build.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Design system · MTI 360",
  robots: { index: false, follow: false },
};

function appEnvOrNull(): string | null {
  try {
    return getServerEnv().appEnv;
  } catch {
    return null; // invalid configuration: fail closed
  }
}

export default function DesignSystemPage() {
  if (!isShowcaseEnabled(appEnvOrNull() ?? undefined)) notFound();
  return <Showcase />;
}
