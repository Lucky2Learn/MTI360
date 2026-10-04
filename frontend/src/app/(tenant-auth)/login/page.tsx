import { redirect } from "next/navigation";

import { LoginScreen } from "@/features/identity/LoginScreen";
import {
  destinationFor,
  firstParam,
  loginReason,
  safeNextPath,
} from "@/lib/session/routes";
import { readTenantSession } from "@/lib/session/server";

import type { Metadata } from "next";

// AUTH-01 /login (T01-04 UI contract §6, §8.1). Entry check (UX only):
// already signed in → the session's next step. `next` and `reason` are
// allow-listed; anything else is ignored.
export const metadata: Metadata = { title: "Sign in · MTI 360" };
export const dynamic = "force-dynamic";

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function LoginPage({ searchParams }: Props) {
  const params = await searchParams;
  const next = safeNextPath(firstParam(params.next));
  // An unreadable session is treated as none: sign-in itself reports errors.
  const session = await readTenantSession().catch(() => null);
  if (session && session.status !== "mfa_required") {
    redirect(destinationFor(session.status, next));
  }
  return (
    <LoginScreen reason={loginReason(firstParam(params.reason))} next={next} />
  );
}
