import type { PlatformSessionWire } from "@/lib/api/types";
import { unreleasedVisible } from "@/lib/authz/requirements";
import { getServerEnv } from "@/lib/env";
import {
  readPlatformSession,
  SessionReadError,
} from "@/lib/session/platform-server";

import { PlatformFrame } from "./platform-frame";

import type { ReactNode } from "react";

// Platform console (/platform, /platform/profile and the T00-08 placeholder
// pages): guarded since T01-09B. The platform session is read from the API on
// the server for every request, with ONLY the platform cookie
// (lib/session/platform-server.ts). With a full session the shell renders
// with the permission-filtered navigation; without one (none, expired, MFA
// still pending, or a tenant cookie only) the layout renders no shell and the
// page redirects to /platform/session-ended — the page is the gate.

async function fullSession(): Promise<PlatformSessionWire | null> {
  try {
    return await readPlatformSession();
  } catch (error) {
    // The page's own read fails the same way and shows the error boundary.
    if (error instanceof SessionReadError) return null;
    throw error;
  }
}

export default async function PlatformConsoleLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  const session = await fullSession();
  if (!session) return children;
  return (
    <PlatformFrame
      session={session}
      showUnreleased={unreleasedVisible(getServerEnv().appEnv)}
    >
      {children}
    </PlatformFrame>
  );
}
