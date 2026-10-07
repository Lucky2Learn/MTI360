import { notFound } from "next/navigation";

import { meets, UNRELEASED, unreleasedVisible } from "@/lib/authz/requirements";
import { getServerEnv } from "@/lib/env";
import { PLATFORM_HOME } from "@/lib/session/platform-routes";
import {
  readPlatformSession,
  requirePlatformSession,
} from "@/lib/session/platform-server";
import { PlatformSessionSync } from "@/lib/session/PlatformSessionProvider";
import {
  EXPERIENCE,
  ExperiencePlaceholder,
  resolveExperiencePage,
  ShellAccessDenied,
  type ExperiencePage,
} from "@/shells";

import { PlatformOverview } from "../overview";

import type { Metadata } from "next";

// Platform pages (T00-08 placeholders; guarded since T01-09B). For every
// request, on the server and before any protected content is rendered:
// 1. session: no full platform session (none, expired, revoked, MFA still
//    pending, a tenant cookie only) → /platform/session-ended (requirePlatformSession);
// 2. requirement (the platform navigation's requirement map): unknown route
//    or UNRELEASED outside development → not found; permission absent →
//    access denied at the same URL. Never a role-name check;
// 3. the page. The platform API still authorizes every request it makes.
export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug?: string[] }> };

type Decision =
  | { kind: "not-found" }
  | { kind: "denied" }
  | { kind: "allowed"; page: ExperiencePage };

const PLATFORM_DENIED =
  "Your platform access doesn't include this page. If you need it, ask a Super Admin.";

function pathOf(slug: string[] | undefined): string {
  return slug?.length ? `${PLATFORM_HOME}/${slug.join("/")}` : PLATFORM_HOME;
}

function decide(slug: string[] | undefined, permissions: string[]): Decision {
  const showUnreleased = unreleasedVisible(getServerEnv().appEnv);
  const page = resolveExperiencePage(EXPERIENCE.PLATFORM, slug);
  const requirement = page?.item.requirement;
  if (!page || requirement === undefined) return { kind: "not-found" };
  if (requirement === UNRELEASED && !showUnreleased) {
    return { kind: "not-found" };
  }
  if (!meets(requirement, { permissions, showUnreleased })) {
    return { kind: "denied" };
  }
  return { kind: "allowed", page };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const session = await readPlatformSession().catch(() => null);
  if (!session) return {};
  const decision = decide((await params).slug, session.permissions);
  if (decision.kind === "denied") {
    return { title: "Access denied · Platform Administration · MTI 360" };
  }
  if (decision.kind === "allowed") {
    const { item, experience } = decision.page;
    return { title: `${item.label} · ${experience.label} · MTI 360` };
  }
  return {};
}

export default async function PlatformPage({ params }: Props) {
  const { slug } = await params;
  const session = await requirePlatformSession(pathOf(slug));
  const decision = decide(slug, session.permissions);
  if (decision.kind === "not-found") notFound();

  return (
    <>
      <PlatformSessionSync session={session} />
      {decision.kind === "denied" ? (
        <ShellAccessDenied
          homeHref={PLATFORM_HOME}
          homeLabel="Go to overview"
          description={PLATFORM_DENIED}
        />
      ) : decision.page.isHome ? (
        <PlatformOverview />
      ) : (
        <ExperiencePlaceholder page={decision.page} />
      )}
    </>
  );
}
