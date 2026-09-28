import { notFound } from "next/navigation";

import {
  EXPERIENCE,
  ExperiencePlaceholder,
  experienceStaticParams,
  resolveExperiencePage,
} from "@/shells";

import type { Metadata } from "next";

// Placeholder pages of the experience (T00-08): exactly the pages in its
// navigation configuration; every other path is a 404.
export const dynamicParams = false;

export function generateStaticParams() {
  return experienceStaticParams(EXPERIENCE.STUDENT);
}

type Props = { params: Promise<{ slug?: string[] }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const page = resolveExperiencePage(EXPERIENCE.STUDENT, (await params).slug);
  return page
    ? { title: `${page.item.label} · ${page.experience.label} · MTI 360` }
    : {};
}

export default async function StudentPage({ params }: Props) {
  const page = resolveExperiencePage(EXPERIENCE.STUDENT, (await params).slug);
  if (!page) notFound();
  return <ExperiencePlaceholder page={page} />;
}
