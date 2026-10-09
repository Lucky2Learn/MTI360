import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
} from "@/design-system/components";
import { DetailTemplate } from "@/design-system/templates/DetailTemplate";
import {
  applicationPath,
  DOCUMENT_READ,
  DOCUMENT_STATUS_LABEL,
  DOCUMENT_STATUS_TONE,
  DOCUMENT_TYPE_LABEL,
  STUDENT_READ,
  STUDENTS_PATH,
  studentPath,
} from "@/features/applications/labels";
import { CATEGORY_LABEL } from "@/features/courses/labels";
import { DownloadLink } from "@/features/documents/DocumentsPanel";
import { formatDate } from "@/features/shared/format";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import { RecordLink } from "@/features/shared/RecordLink";
import { StudentTimeline } from "@/features/students/StudentTimeline";
import type {
  StudentDocumentWire,
  StudentWire,
  TimelineEntryWire,
} from "@/lib/api/admissions";
import { tenantApiRead } from "@/lib/api/server-read";
import { can } from "@/lib/authz/requirements";
import {
  requireRecordId,
  settle,
  tenantPageAccess,
} from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { PageContainer, ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";
import type { ReactNode } from "react";

// ADM-12 Student profile (Student 360), /app/admissions/students/[id] (Phase
// 02-2; ADR-0021 §6, §14) with ADM-13 Admissions and ADM-14 Documents as its
// sections. Batch, attendance, fees, training, exams, certificates, placement
// and communication arrive with their modules: an intentional empty state
// says so instead of showing invented data. Read-only in the MVP.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Student · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ studentId: string }> };

const LATER = [
  "Batch",
  "Attendance",
  "Fees",
  "Training",
  "Exams",
  "Certificates",
  "Placement",
  "Communication",
];

function Term({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 tablet:flex-row tablet:gap-6">
      <dt className="text-body-sm text-text-secondary tablet:w-40 tablet:shrink-0">
        {term}
      </dt>
      <dd className="min-w-0 text-body-sm break-words text-text-primary">
        {children}
      </dd>
    </div>
  );
}

function Personal({ student }: { student: StudentWire }) {
  return (
    <Card as="section">
      <CardHeader title="Personal" titleAs="h2" />
      <CardBody>
        <dl className="flex flex-col gap-4">
          <Term term="Student number">{student.student_number}</Term>
          <Term term="Date of birth">
            {student.date_of_birth
              ? formatDate(student.date_of_birth)
              : "Not given"}
          </Term>
          <Term term="Mobile">{student.mobile ?? "Not given"}</Term>
          <Term term="Email">{student.email ?? "Not given"}</Term>
          <Term term="City">{student.city ?? "Not given"}</Term>
          <Term term="Home campus">{student.home_campus.name}</Term>
          <Term term="Student since">
            {`${formatDate(student.created_at)}${student.created_by ? ` · ${student.created_by.display_name}` : ""}`}
          </Term>
        </dl>
      </CardBody>
    </Card>
  );
}

function Admissions({ student }: { student: StudentWire }) {
  return (
    <Card as="section">
      <CardHeader title="Admissions" titleAs="h2" />
      <CardBody>
        {student.admissions.length === 0 ? (
          <EmptyState
            title="No admissions in your campuses"
            description="Admissions at campuses you don't work with are not shown."
          />
        ) : (
          <ul className="flex flex-col gap-4">
            {student.admissions.map((admission) => (
              <li key={admission.id} className="flex flex-col gap-1">
                <span className="flex flex-wrap items-center gap-2 text-body-sm font-medium text-text-primary">
                  {`${admission.course_code} · ${admission.course_name}`}
                  <Badge tone="success">Admitted</Badge>
                </span>
                <span className="text-caption text-text-secondary">
                  {`${admission.admission_number} · ${CATEGORY_LABEL[admission.course_category]} · ${admission.campus.name} · ${formatDate(admission.approved_at)}`}
                </span>
                <span className="text-caption">
                  <RecordLink href={applicationPath(admission.application_id)}>
                    {`Application ${admission.application_number}`}
                  </RecordLink>
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

function Documents({ documents }: { documents: StudentDocumentWire[] }) {
  return (
    <Card as="section">
      <CardHeader title="Documents" titleAs="h2" />
      <CardBody>
        {documents.length === 0 ? (
          <EmptyState
            title="No documents"
            description="Documents of the student's applications appear here."
          />
        ) : (
          <ul className="flex flex-col gap-3">
            {documents.map((document) => (
              <li key={document.id} className="flex min-w-0 flex-col gap-1">
                <span className="flex flex-wrap items-center gap-2 text-body-sm text-text-primary">
                  {DOCUMENT_TYPE_LABEL[document.document_type]}
                  <Badge tone={DOCUMENT_STATUS_TONE[document.status]}>
                    {DOCUMENT_STATUS_LABEL[document.status]}
                  </Badge>
                </span>
                <DownloadLink document={document} />
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

function LaterModules() {
  return (
    <Card as="section">
      <CardHeader title="More about this student" titleAs="h2" />
      <CardBody>
        <EmptyState
          title="Coming with later modules"
          description={`${LATER.join(", ")} appear here when those modules are set up for your institute.`}
        />
      </CardBody>
    </Card>
  );
}

export default async function StudentPage({ params }: Props) {
  const id = requireRecordId((await params).studentId);
  const path = studentPath(id);
  const { session, allowed } = await tenantPageAccess(path, STUDENT_READ);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const [read, documentsRead, timelineRead] = await Promise.all([
    tenantApiRead<StudentWire>(`/students/${id}`),
    can(session.permissions, DOCUMENT_READ)
      ? tenantApiRead<{ items: StudentDocumentWire[] }>(
          `/students/${id}/documents`,
        )
      : null,
    tenantApiRead<TimelineEntryWire[]>(`/students/${id}/activity?limit=50`),
  ]);
  const result = settle(read, path);
  if (result.kind !== "ok") {
    return (
      <>
        <SessionSync session={session} />
        {result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <PageContainer>
            <ReadErrorState
              title="This student couldn't be loaded"
              reference={result.reference}
            />
          </PageContainer>
        )}
      </>
    );
  }
  const student = result.data;
  return (
    <>
      <SessionSync session={session} />
      <DetailTemplate
        title={student.full_name}
        description={`${student.student_number} · ${student.home_campus.name}`}
        breadcrumbs={[
          { label: "Admissions" },
          { label: "Students", href: STUDENTS_PATH },
          { label: student.student_number },
        ]}
        status={<Badge tone="success">Active</Badge>}
        asideLabel="Admissions and documents"
        main={
          <>
            <Personal student={student} />
            <LaterModules />
          </>
        }
        aside={
          <>
            <Admissions student={student} />
            {documentsRead === null ? null : documentsRead.kind === "ok" ? (
              <Documents documents={documentsRead.data.items} />
            ) : (
              <ReadErrorState
                title="Documents couldn't be loaded"
                reference={null}
              />
            )}
          </>
        }
      >
        <Card as="section">
          <CardHeader title="History" titleAs="h2" />
          <CardBody>
            {timelineRead.kind === "ok" ? (
              timelineRead.data.length > 0 ? (
                <StudentTimeline entries={timelineRead.data} />
              ) : (
                <EmptyState
                  title="No history to show"
                  description="Enquiry and application history appears here for members who may read leads and applications."
                />
              )
            ) : (
              <ReadErrorState
                title="History couldn't be loaded"
                reference={null}
              />
            )}
          </CardBody>
        </Card>
      </DetailTemplate>
    </>
  );
}
