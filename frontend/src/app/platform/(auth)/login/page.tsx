import { redirect } from "next/navigation";

import { PlatformLoginScreen } from "@/features/platform-identity/PlatformLoginScreen";
import {
  platformLoginReason,
  resolvePlatformNext,
  safePlatformNextPath,
} from "@/lib/session/platform-routes";
import { readPlatformSession } from "@/lib/session/platform-server";
import { firstParam } from "@/lib/session/routes";

import type { Metadata } from "next";

// PLAT-01 /platform/login (T01-09B UI contract §4, §6). Entry check (UX
// only): a full platform session goes to `next` or /platform. An MFA-pending
// or absent session shows the form — the pending state is never restored
// (D9B-2). `next` and `reason` are allow-listed; anything else is ignored.
export const metadata: Metadata = { title: "Sign in · MTI 360 Platform" };
export const dynamic = "force-dynamic";

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function PlatformLoginPage({ searchParams }: Props) {
  const params = await searchParams;
  const next = safePlatformNextPath(firstParam(params.next));
  // An unreadable session is treated as none: sign-in itself reports errors.
  const session = await readPlatformSession().catch(() => null);
  if (session) redirect(resolvePlatformNext(next));
  return (
    <PlatformLoginScreen
      reason={platformLoginReason(firstParam(params.reason))}
      next={next}
    />
  );
}
