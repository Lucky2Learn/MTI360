import { DataListTemplate } from "@/design-system/templates/DataListTemplate";
import { STUDENT_READ, STUDENTS_PATH } from "@/features/applications/labels";
import { studentListQuery } from "@/features/applications/query";
import type { SearchParams } from "@/features/courses/query";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import { StudentList } from "@/features/students/StudentList";
import type { StudentListItemWire } from "@/lib/api/admissions";
import { tenantApiRead } from "@/lib/api/server-read";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// ADM-11 Students, /app/admissions/students (Phase 02-2; ADR-0021 §6, §14).
// Gate: ready session → student.read → the list read on the server; the API
// shows the students of the member's campuses (home campus).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Students · Tenant Application · MTI 360",
};

export default async function StudentsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { session, allowed } = await tenantPageAccess(
    STUDENTS_PATH,
    STUDENT_READ,
  );
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const query = studentListQuery(await searchParams);
  const result = settle(
    await tenantApiRead<StudentListItemWire[]>(`/students?${query}`),
    STUDENTS_PATH,
  );
  return (
    <>
      <SessionSync session={session} />
      <DataListTemplate
        title="Students"
        description="Admitted students of your campuses."
        breadcrumbs={[{ label: "Admissions" }, { label: "Students" }]}
      >
        {result.kind === "ok" ? (
          <StudentList
            students={result.data}
            page={
              result.page ?? { limit: 25, offset: 0, total: result.data.length }
            }
          />
        ) : result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <ReadErrorState
            title="Students couldn't be loaded"
            reference={result.reference}
          />
        )}
      </DataListTemplate>
    </>
  );
}
