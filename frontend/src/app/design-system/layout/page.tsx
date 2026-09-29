import { notFound } from "next/navigation";

import { getServerEnv } from "@/lib/env";

import { isShowcaseEnabled } from "../gate";

import { LayoutExample } from "./layout-example";

import type { Metadata } from "next";

// /design-system/layout — T00-09 in-shell layout example. Same gate as the
// component showcase: development and test only, 404 otherwise (fail closed).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Layout examples · Design system · MTI 360",
  robots: { index: false, follow: false },
};

function appEnvOrNull(): string | null {
  try {
    return getServerEnv().appEnv;
  } catch {
    return null; // invalid configuration: fail closed
  }
}

export default function LayoutExamplePage() {
  if (!isShowcaseEnabled(appEnvOrNull() ?? undefined)) notFound();
  return <LayoutExample />;
}
