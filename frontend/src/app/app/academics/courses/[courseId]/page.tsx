import { Badge, Card, CardBody, CardHeader } from "@/design-system/components";
import { DetailTemplate } from "@/design-system/templates/DetailTemplate";
import { CourseActions } from "@/features/courses/CourseActions";
import {
  CATEGORY_LABEL,
  COURSE_READ,
  COURSES_PATH,
  coursePath,
  durationLabel,
  STATUS_LABEL,
  STATUS_TONE,
} from "@/features/courses/labels";
import { formatDate } from "@/features/shared/format";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { CourseWire } from "@/lib/api/admissions";
import { tenantApiRead } from "@/lib/api/server-read";
import {
  requireRecordId,
  settle,
  tenantPageAccess,
} from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { PageContainer, ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";
import type { ReactNode } from "react";

// ACA-02 Course detail, /app/academics/courses/[courseId] (Phase 02-1). A
// course of another institute, or a malformed ID, is RESOURCE-02 (the API
// answers 404 for both missing and other-tenant courses). Actions need
// course.manage (PermissionGate; the API decides).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Course · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ courseId: string }> };

function Term({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 tablet:flex-row tablet:gap-6">
      <dt className="text-body-sm text-text-secondary tablet:w-40 tablet:shrink-0">
        {term}
      </dt>
      <dd className="min-w-0 text-body-sm break-words whitespace-pre-wrap text-text-primary">
        {children}
      </dd>
    </div>
  );
}

export default async function CourseDetailPage({ params }: Props) {
  const id = requireRecordId((await params).courseId);
  const path = coursePath(id);
  const { session, allowed } = await tenantPageAccess(path, COURSE_READ);
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
  if (result.kind !== "ok") {
    return (
      <>
        <SessionSync session={session} />
        {result.kind === "denied" ? (
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
  const course = result.data;
  return (
    <>
      <SessionSync session={session} />
      <DetailTemplate
        title={course.name}
        description={`${course.code} · ${CATEGORY_LABEL[course.category]}`}
        breadcrumbs={[
          { label: "Academics" },
          { label: "Courses", href: COURSES_PATH },
          { label: course.code },
        ]}
        status={
          <Badge tone={STATUS_TONE[course.status]}>
            {STATUS_LABEL[course.status]}
          </Badge>
        }
        actions={<CourseActions course={course} />}
        asideLabel="Course summary"
        main={
          <Card as="section">
            <CardHeader title="About this course" titleAs="h2" />
            <CardBody>
              <dl className="flex flex-col gap-4">
                <Term term="Eligibility">
                  {course.eligibility_summary ?? "Not recorded yet."}
                </Term>
                <Term term="Description">
                  {course.description ?? "Not recorded yet."}
                </Term>
              </dl>
            </CardBody>
          </Card>
        }
        aside={
          <Card as="section">
            <CardHeader title="Summary" titleAs="h2" />
            <CardBody>
              <dl className="flex flex-col gap-4">
                <Term term="Code">{course.code}</Term>
                <Term term="Category">{CATEGORY_LABEL[course.category]}</Term>
                <Term term="Duration">
                  {durationLabel(course) ?? "Not set"}
                </Term>
                <Term term="Status">{STATUS_LABEL[course.status]}</Term>
                <Term term="Last updated">{formatDate(course.updated_at)}</Term>
              </dl>
            </CardBody>
          </Card>
        }
      />
    </>
  );
}
