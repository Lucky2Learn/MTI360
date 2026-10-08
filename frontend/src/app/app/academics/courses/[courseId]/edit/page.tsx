import { CourseForm } from "@/features/courses/CourseForm";
import {
  COURSE_MANAGE,
  COURSES_PATH,
  coursePath,
} from "@/features/courses/labels";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { CourseWire } from "@/lib/api/admissions";
import { tenantApiRead } from "@/lib/api/server-read";
import {
  requireRecordId,
  settle,
  tenantPageAccess,
} from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import {
  PageContainer,
  PageContent,
  PageHeader,
  ShellAccessDenied,
} from "@/shells";

import type { Metadata } from "next";

// ACA-03 Edit course, /app/academics/courses/[courseId]/edit (Phase 02-1).
// course.manage; the code is shown read-only; the loaded version guards
// against lost updates (409 → "changed by someone else").
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Edit course · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ courseId: string }> };

export default async function EditCoursePage({ params }: Props) {
  const id = requireRecordId((await params).courseId);
  const path = `${coursePath(id)}/edit`;
  const { session, allowed } = await tenantPageAccess(path, COURSE_MANAGE);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const result = settle(
    await tenantApiRead<CourseWire>(`/courses/${id}`),
    path,
  );
  return (
    <>
      <SessionSync session={session} />
      {result.kind === "ok" ? (
        <PageContainer width="standard">
          <PageHeader
            title={`Edit ${result.data.name}`}
            breadcrumbs={[
              { label: "Academics" },
              { label: "Courses", href: COURSES_PATH },
              { label: result.data.code, href: coursePath(id) },
              { label: "Edit" },
            ]}
          />
          <PageContent>
            <CourseForm course={result.data} />
          </PageContent>
        </PageContainer>
      ) : result.kind === "denied" ? (
        <ShellAccessDenied homeHref="/app" />
      ) : (
        <PageContainer>
          <ReadErrorState
            title="This course couldn't be loaded"
            reference={result.reference}
          />
        </PageContainer>
      )}
    </>
  );
}
