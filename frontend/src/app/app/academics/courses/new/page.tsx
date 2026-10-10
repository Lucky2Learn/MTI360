import { CourseForm } from "@/features/courses/CourseForm";
import { COURSE_MANAGE, COURSES_PATH } from "@/features/courses/labels";
import { tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import {
  PageContainer,
  PageContent,
  PageHeader,
  ShellAccessDenied,
} from "@/shells";

import type { Metadata } from "next";

// ACA-03 Create course, /app/academics/courses/new (Phase 02-1). course.manage
// is tenant-wide: campus-restricted members see AUTHZ-01 here (and the API
// refuses the request regardless).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "New course · Tenant Application · MTI 360",
};

const PATH = `${COURSES_PATH}/new`;

export default async function NewCoursePage() {
  const { session, allowed } = await tenantPageAccess(PATH, COURSE_MANAGE);
  return (
    <>
      <SessionSync session={session} />
      {allowed ? (
        <PageContainer width="standard">
          <PageHeader
            title="New course"
            description="New courses start as drafts. Activate a course when counsellors may offer it."
            breadcrumbs={[
              { label: "Academics" },
              { label: "Courses", href: COURSES_PATH },
              { label: "New course" },
            ]}
          />
          <PageContent>
            <CourseForm />
          </PageContent>
        </PageContainer>
      ) : (
        <ShellAccessDenied homeHref="/app" />
      )}
    </>
  );
}
