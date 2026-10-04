import { SessionEndedScreen } from "@/features/identity/SessionEndedScreen";
import {
  firstParam,
  safeNextPath,
  sessionEndedReason,
} from "@/lib/session/routes";

import type { Metadata } from "next";

// AUTH-05 /session-ended (T01-04 UI contract §8.7). Never redirects by itself.
export const metadata: Metadata = { title: "Session ended · MTI 360" };

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function SessionEndedPage({ searchParams }: Props) {
  const params = await searchParams;
  return (
    <SessionEndedScreen
      reason={sessionEndedReason(firstParam(params.reason))}
      next={safeNextPath(firstParam(params.next))}
    />
  );
}
