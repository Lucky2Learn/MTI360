import { redirect } from "next/navigation";

import { SelectInstituteScreen } from "@/features/identity/SelectInstituteScreen";
import {
  AUTH_ROUTES,
  authUrl,
  destinationFor,
  firstParam,
  safeNextPath,
} from "@/lib/session/routes";
import { readTenantSession } from "@/lib/session/server";

import type { Metadata } from "next";

// AUTH-07 /select-institute (T01-04 UI contract §6, §8.5). Entry check (UX
// only): not signed in → /login; exactly one institute and it is active →
// the session's next step. The options come only from the server session.
export const metadata: Metadata = { title: "Choose an institute · MTI 360" };
export const dynamic = "force-dynamic";

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function SelectInstitutePage({ searchParams }: Props) {
  const next = safeNextPath(firstParam((await searchParams).next));
  const session = await readTenantSession();
  if (!session || session.status === "mfa_required") {
    redirect(authUrl(AUTH_ROUTES.login, { next }));
  }
  if (session.active_institute && session.institutes.length === 1) {
    redirect(destinationFor(session.status, next));
  }
  return <SelectInstituteScreen session={session} next={next} />;
}
