import { notFound } from "next/navigation";

import { EmptyState } from "@/design-system/components";
import { CompassIcon } from "@/design-system/icons";
import { meets, UNRELEASED, unreleasedVisible } from "@/lib/authz/requirements";
import { getServerEnv } from "@/lib/env";
import {
  readTenantSession,
  requireReadyTenantSession,
} from "@/lib/session/server";
import { SessionSync } from "@/lib/session/SessionProvider";
import {
  EXPERIENCE,
  ExperiencePlaceholder,
  PageContainer,
  PageContent,
  PageHeader,
  resolveExperiencePage,
  ShellAccessDenied,
  type ExperiencePage,
} from "@/shells";

import type { Metadata } from "next";

// Tenant pages (T00-08 placeholders; guarded since T01-09A). For every
// request, on the server and before any protected content is rendered
// (T01-05 UI contract §7, S9):
// 1. session: none → /session-ended; no institute → /select-institute;
//    campus choice required → /select-campus (requireReadyTenantSession);
// 2. requirement (the navigation's requirement map, §6): unknown route or
//    UNRELEASED outside development/test → RESOURCE-02 (not-found.tsx);
//    permission absent → AUTHZ-01, at the same URL;
// 3. the page. The API still authorizes every data request it makes.
export const dynamic = "force-dynamic";

const HOME = "/app";

type Props = { params: Promise<{ slug?: string[] }> };

type Decision =
  | { kind: "not-found" }
  | { kind: "denied" }
  | { kind: "allowed"; page: ExperiencePage };

function pathOf(slug: string[] | undefined): string {
  return slug?.length ? `${HOME}/${slug.join("/")}` : HOME;
}

function decide(slug: string[] | undefined, permissions: string[]): Decision {
  const showUnreleased = unreleasedVisible(getServerEnv().appEnv);
  const page = resolveExperiencePage(EXPERIENCE.TENANT, slug);
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
  const session = await readTenantSession().catch(() => null);
  if (session?.status !== "ready") return {};
  const decision = decide((await params).slug, session.permissions);
  if (decision.kind === "denied") {
    return { title: "Access denied · Tenant Application · MTI 360" };
  }
  if (decision.kind === "allowed") {
    const { item, experience } = decision.page;
    return { title: `${item.label} · ${experience.label} · MTI 360` };
  }
  return {};
}

/** DASH-01 (T01-05 §8.6): no released section yet, so the empty state. */
function TenantDashboard() {
  return (
    <PageContainer width="wide">
      <PageHeader title="Dashboard" />
      <PageContent>
        <EmptyState
          titleAs="h2"
          icon={CompassIcon}
          title="Your dashboard is empty for now"
          description="Sections appear here as your institute uses MTI 360 and your access includes them."
        />
      </PageContent>
    </PageContainer>
  );
}

export default async function TenantPage({ params }: Props) {
  const { slug } = await params;
  const session = await requireReadyTenantSession(pathOf(slug));
  const decision = decide(slug, session.permissions);
  if (decision.kind === "not-found") notFound();

  return (
    <>
      <SessionSync session={session} />
      {decision.kind === "denied" ? (
        <ShellAccessDenied homeHref={HOME} />
      ) : decision.page.isHome ? (
        <TenantDashboard />
      ) : (
        <ExperiencePlaceholder page={decision.page} />
      )}
    </>
  );
}
