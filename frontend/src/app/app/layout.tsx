import type { SessionWire } from "@/lib/api/types";
import { unreleasedVisible } from "@/lib/authz/requirements";
import { getServerEnv } from "@/lib/env";
import { readTenantSession, SessionReadError } from "@/lib/session/server";

import { TenantFrame } from "./tenant-frame";

import type { Metadata } from "next";
import type { ReactNode } from "react";

// Tenant Application (/app): one Maritime Training Institute's workspace.
// Route boundary (T00-08), guarded since T01-09A. The session is read from
// the API on the server for every request (lib/session/server.ts). With a
// ready session the shell renders with the permission-filtered navigation.
// Without one the layout renders no shell and the page redirects (the page
// knows the requested path, which becomes `next`) — the page is the gate on
// every navigation (T01-05 UI contract §7). Pages are not indexed.
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

async function readySession(): Promise<SessionWire | null> {
  try {
    const session = await readTenantSession();
    return session?.status === "ready" ? session : null;
  } catch (error) {
    // The page's own read fails the same way and shows the error boundary.
    if (error instanceof SessionReadError) return null;
    throw error;
  }
}

export default async function TenantLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  const session = await readySession();
  if (!session) return children;
  return (
    <TenantFrame
      session={session}
      showUnreleased={unreleasedVisible(getServerEnv().appEnv)}
    >
      {children}
    </TenantFrame>
  );
}
