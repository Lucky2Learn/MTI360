import { Alert, Button, EmptyState } from "@/design-system/components";
import {
  STUDENT_READ,
  STUDENTS_PATH,
  studentPath,
} from "@/features/applications/labels";
import { first } from "@/features/courses/query";
import { InvoiceIssueForm } from "@/features/finance/InvoiceIssueForm";
import {
  FEE_STRUCTURE_READ,
  INVOICE_ISSUE,
  INVOICES_PATH,
  invoicePath,
  STRUCTURES_PATH,
} from "@/features/finance/labels";
import { isRecordId, type SearchParams } from "@/features/finance/query";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { StudentWire } from "@/lib/api/admissions";
import type { FeeStructureWire, InvoiceWire } from "@/lib/api/finance";
import { tenantApiRead } from "@/lib/api/server-read";
import { can } from "@/lib/authz/requirements";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import {
  PageContainer,
  PageContent,
  PageHeader,
  ShellAccessDenied,
} from "@/shells";

import type { Metadata } from "next";
import type { ReactNode } from "react";

// Issue a fee invoice, /app/finance/invoices/new?student=…&admission=…
// (Phase 02-5; readiness plan J2). The admission is the billing context, so
// the page is opened from the student's profile. Gate: invoice.issue; the
// student is read with student.read (finance roles hold it), its admission
// must be one the caller sees, and the course needs an active fee structure.
// An existing live fee invoice for the admission is shown instead of the
// form. The API re-checks all of it when the form is sent.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Issue fee invoice · Tenant Application · MTI 360",
};

const PATH = `${INVOICES_PATH}/new`;
const LIVE = new Set(["ISSUED", "PARTIALLY_PAID", "PAID"]);

function Frame({
  description,
  studentCrumb,
  children,
}: {
  description?: string;
  studentCrumb?: { label: string; href: string };
  children: ReactNode;
}) {
  return (
    <PageContainer width="standard">
      <PageHeader
        title="Issue fee invoice"
        description={description}
        breadcrumbs={[
          { label: "Finance" },
          { label: "Fee invoices", href: INVOICES_PATH },
          ...(studentCrumb ? [studentCrumb] : []),
          { label: "Issue fee invoice" },
        ]}
      />
      <PageContent>{children}</PageContent>
    </PageContainer>
  );
}

export default async function IssueInvoicePage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { session, allowed } = await tenantPageAccess(PATH, INVOICE_ISSUE);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const params = await searchParams;
  const studentId = first(params.student);
  const admissionId = first(params.admission);
  const readsStudents = can(session.permissions, STUDENT_READ);

  if (!isRecordId(studentId) || !isRecordId(admissionId) || !readsStudents) {
    return (
      <>
        <SessionSync session={session} />
        <Frame>
          <EmptyState
            title="Start from an admitted student"
            description={
              readsStudents
                ? "A fee invoice belongs to a student's admission. Open the student's profile and choose Raise fee invoice in the Fees section."
                : "A fee invoice belongs to a student's admission. Ask a colleague who can open student profiles to raise it."
            }
            primaryAction={
              readsStudents ? (
                <Button href={STUDENTS_PATH}>Go to students</Button>
              ) : undefined
            }
          />
        </Frame>
      </>
    );
  }

  const studentRead = settle(
    await tenantApiRead<StudentWire>(`/students/${studentId}`),
    PATH,
  );
  if (studentRead.kind !== "ok") {
    return (
      <>
        <SessionSync session={session} />
        {studentRead.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <Frame>
            <ReadErrorState
              title="The student couldn't be loaded"
              reference={studentRead.reference}
            />
          </Frame>
        )}
      </>
    );
  }
  const student = studentRead.data;
  const admission = student.admissions.find((item) => item.id === admissionId);
  const crumb = {
    label: student.student_number,
    href: studentPath(student.id),
  };
  const description = admission
    ? `${student.full_name} · ${student.student_number} · ${admission.admission_number} · ${admission.course_code} · ${admission.campus.name}`
    : undefined;
  if (!admission) {
    return (
      <>
        <SessionSync session={session} />
        <Frame studentCrumb={crumb}>
          <Alert tone="warning" title="This admission isn't available">
            Choose an admission of this student at one of your campuses, from
            the student&apos;s profile.
          </Alert>
        </Frame>
      </>
    );
  }

  const [structures, invoices] = await Promise.all([
    can(session.permissions, FEE_STRUCTURE_READ)
      ? tenantApiRead<FeeStructureWire[]>(
          `/fee-structures?course_id=${admission.course_id}&status=ACTIVE&limit=1`,
        )
      : null,
    tenantApiRead<InvoiceWire[]>(
      `/invoices?student_id=${student.id}&limit=100&sort=-issued_at`,
    ),
  ]);
  const live =
    invoices.kind === "ok"
      ? invoices.data.find(
          (item) => item.admission.id === admission.id && LIVE.has(item.status),
        )
      : undefined;
  let content: ReactNode;
  if (live) {
    content = (
      <Alert tone="info" title="This admission already has a fee invoice">
        <span className="flex flex-col items-start gap-3">
          {`${live.number} is live. Cancel it first to issue a replacement, which gets a new number.`}
          <Button variant="secondary" href={invoicePath(live.id)}>
            {`Open ${live.number}`}
          </Button>
        </span>
      </Alert>
    );
  } else if (structures === null || structures.kind !== "ok") {
    content =
      structures?.kind === "error" ? (
        <ReadErrorState
          title="The fee structure couldn't be loaded"
          reference={structures.reference}
        />
      ) : (
        <Alert tone="warning" title="The fee structure can't be read">
          Issuing a fee invoice needs access to fee structures. Ask your
          institute administrator.
        </Alert>
      );
  } else if (structures.data.length === 0) {
    content = (
      <Alert tone="warning" title="The course has no active fee structure">
        <span className="flex flex-col items-start gap-3">
          {`Activate a fee structure for ${admission.course_code} · ${admission.course_name} first.`}
          <Button variant="secondary" href={STRUCTURES_PATH}>
            Go to fee structures
          </Button>
        </span>
      </Alert>
    );
  } else {
    content = (
      <InvoiceIssueForm
        admission={{ id: admission.id, number: admission.admission_number }}
        structure={structures.data[0]!}
        cancelHref={studentPath(student.id)}
      />
    );
  }
  return (
    <>
      <SessionSync session={session} />
      <Frame description={description} studentCrumb={crumb}>
        {content}
      </Frame>
    </>
  );
}
