import { SessionEndedScreen } from "@/features/identity/SessionEndedScreen";
import { safePlatformNextPath } from "@/lib/session/platform-routes";
import { firstParam, sessionEndedReason } from "@/lib/session/routes";

import type { Metadata } from "next";

// PAUTH-06 /platform/session-ended (T01-09B UI contract §7). Never redirects
// by itself; `reason` is the AUTH-05 allow-list and `next` the platform one.
export const metadata: Metadata = {
  title: "Session ended · MTI 360 Platform",
};

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function PlatformSessionEndedPage({
  searchParams,
}: Props) {
  const params = await searchParams;
  return (
    <SessionEndedScreen
      realm="platform"
      reason={sessionEndedReason(firstParam(params.reason))}
      next={safePlatformNextPath(firstParam(params.next))}
    />
  );
}
