import { redirect } from "next/navigation";

import { SelectCampusScreen } from "@/features/identity/SelectCampusScreen";
import {
  AUTH_ROUTES,
  authUrl,
  CAMPUS_UNAVAILABLE_REASON,
  firstParam,
  resolveNext,
  safeNextPath,
} from "@/lib/session/routes";
import { readTenantSession } from "@/lib/session/server";

import type { Metadata } from "next";

// AUTH-08 /select-campus (T01-04 UI contract §6, §8.6; D04). Entry check (UX
// only): not signed in → /login; no institute → /select-institute; no
// campus choice required → `next` or /app.
export const metadata: Metadata = { title: "Choose a campus · MTI 360" };
export const dynamic = "force-dynamic";

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function SelectCampusPage({ searchParams }: Props) {
  const params = await searchParams;
  const next = safeNextPath(firstParam(params.next));
  const session = await readTenantSession();
  if (!session || session.status === "mfa_required") {
    redirect(authUrl(AUTH_ROUTES.login, { next }));
  }
  if (!session.active_institute) {
    redirect(authUrl(AUTH_ROUTES.selectInstitute, { next }));
  }
  if (!session.campus_selection_required) redirect(resolveNext(next));
  return (
    <SelectCampusScreen
      session={session}
      next={next}
      campusWithdrawn={firstParam(params.reason) === CAMPUS_UNAVAILABLE_REASON}
    />
  );
}
