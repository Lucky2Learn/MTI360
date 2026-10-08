import { DataListTemplate } from "@/design-system/templates/DataListTemplate";
import { CourseList, NewCourseButton } from "@/features/courses/CourseList";
import { COURSE_READ, COURSES_PATH } from "@/features/courses/labels";
import { courseListQuery, type SearchParams } from "@/features/courses/query";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { CourseWire } from "@/lib/api/admissions";
import { tenantApiRead } from "@/lib/api/server-read";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// ACA-01 Courses, /app/academics/courses (Phase 02-1; blueprint §20-§21).
// Gate: ready session → course.read (AUTHZ-01 at this URL otherwise) → the
// catalogue read on the server with the tenant cookie only. The API
// authorizes the read again; courses are institute-wide, so campus-restricted
// staff see the whole catalogue.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Courses · Tenant Application · MTI 360",
};

const BREADCRUMBS = [{ label: "Academics" }, { label: "Courses" }];

export default async function CoursesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { session, allowed } = await tenantPageAccess(
    COURSES_PATH,
    COURSE_READ,
  );
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const query = courseListQuery(await searchParams);
  const result = settle(
    await tenantApiRead<CourseWire[]>(`/courses?${query}`),
    COURSES_PATH,
  );
  return (
    <>
      <SessionSync session={session} />
      <DataListTemplate
        title="Courses"
        description="Your institute's course catalogue. Counsellors record which course an enquirer is interested in."
        breadcrumbs={BREADCRUMBS}
        actions={<NewCourseButton />}
      >
        {result.kind === "ok" ? (
          <CourseList
            courses={result.data}
            page={
              result.page ?? { limit: 25, offset: 0, total: result.data.length }
            }
          />
        ) : result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <ReadErrorState
            title="Courses couldn't be loaded"
            reference={result.reference}
          />
        )}
      </DataListTemplate>
    </>
  );
}
