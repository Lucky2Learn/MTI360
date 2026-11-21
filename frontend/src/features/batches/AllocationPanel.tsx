"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  DataTable,
  Dialog,
  Form,
  Select,
  SkeletonText,
  Tab,
  TabList,
  TabPanel,
  Tabs,
  Textarea,
  type DataTableColumn,
} from "@/design-system/components";
import { AddIcon } from "@/design-system/icons";
import type { AllocationWire, BatchWire } from "@/lib/api/batches";
import type { FormFeedback } from "@/lib/authz/action-feedback";
import { PermissionGate } from "@/lib/authz/PermissionGate";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { useFinanceMutation } from "../finance/mutations";
import { ReasonDialog, type ReasonOutcome } from "../finance/ReasonDialog";
import { formatDate } from "../shared/format";
import { focusFirstInvalid } from "../shared/forms";
import { RecordLink } from "../shared/RecordLink";

import { AllocateDialog } from "./AllocateDialog";
import {
  BASIS_LABEL,
  BASIS_TONE,
  BATCH_ALLOCATE,
  END_REASON_LABEL,
  INVOICE_STATE_LABEL,
  outstandingLabel,
} from "./labels";

// ACA-06 Allocated students and allocation history (Phase 02-6). Active
// allocations first; ended ones keep their reason, who and when. With
// batch.allocate: allocate (open batch with free seats), transfer to another
// open batch of the same course and campus, withdraw (reason required; the
// admission returns to ADMITTED). The server re-checks everything with the
// rows locked; a stale allocation (409) refreshes the page.

const studentPath = (id: string) => `/app/admissions/students/${id}`;

export function PaymentNote({ allocation }: { allocation: AllocationWire }) {
  const override = allocation.payment_override;
  return (
    <div className="flex min-w-0 flex-col items-start gap-1">
      <Badge tone={BASIS_TONE[allocation.payment_basis]}>
        {BASIS_LABEL[allocation.payment_basis]}
      </Badge>
      {override && (
        <span className="text-caption break-words text-text-secondary">
          {`${INVOICE_STATE_LABEL[override.invoice_state]} · ${outstandingLabel(override.outstanding_minor)} · “${override.reason}”`}
        </span>
      )}
    </div>
  );
}

function TransferForm({
  allocation,
  batch,
  onClose,
}: {
  allocation: AllocationWire;
  batch: BatchWire;
  onClose: () => void;
}) {
  const { request } = useTenantSession();
  const mutate = useFinanceMutation("allocation");
  const formRef = useRef<HTMLDivElement>(null);
  const [targets, setTargets] = useState<BatchWire[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [target, setTarget] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<{ target?: string; reason?: string }>(
    {},
  );
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let live = true;
    const params = new URLSearchParams({
      course_id: batch.course.id,
      campus_id: batch.campus.id,
      status: "OPEN",
      has_seats: "true",
      sort: "start_date",
      limit: "100",
    });
    request<BatchWire[]>(`/batches?${params.toString()}`)
      .then(
        (items) => live && setTargets(items.filter((b) => b.id !== batch.id)),
      )
      .catch(() => live && setLoadFailed(true));
    return () => {
      live = false;
    };
  }, [batch, request]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const next: typeof errors = {};
    if (!target) next.target = "Choose the batch to move to.";
    if (!reason.trim()) next.reason = "Enter a reason.";
    setErrors(next);
    setFeedback(null);
    if (Object.keys(next).length > 0) {
      focusFirstInvalid(formRef.current);
      return;
    }
    setPending(true);
    const outcome = await mutate(
      `/batch-allocations/${allocation.id}/transfer`,
      {
        target_batch_id: target,
        reason: reason.trim(),
        version: allocation.version,
      },
      `${allocation.student.full_name} transferred`,
    );
    setPending(false);
    if (outcome.kind === "done" || outcome.kind === "stale") onClose();
    else if (outcome.kind === "feedback") setFeedback(outcome.feedback);
    else {
      const code = outcome.fields.target_batch_id;
      setErrors({
        target:
          code === "batch_full"
            ? "That batch is full now. Choose another."
            : code === "batch_not_open"
              ? "That batch is no longer open. Choose another."
              : "Choose an open batch of the same course and campus.",
      });
      focusFirstInvalid(formRef.current);
    }
  };

  return (
    <div ref={formRef}>
      <Form
        aria-label="Transfer student"
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        {loadFailed ? (
          <Alert tone="error" title="Batches couldn't be loaded">
            Close this dialog and try again in a moment.
          </Alert>
        ) : targets === null ? (
          <div aria-busy="true" aria-label="Loading batches">
            <SkeletonText lines={2} />
          </div>
        ) : targets.length === 0 ? (
          <Alert tone="info" title="No other open batch with free seats">
            {`Create or reopen a batch of ${batch.course.code} at ${batch.campus.name} first.`}
          </Alert>
        ) : (
          <Select
            label="Move to batch"
            options={targets.map((b) => ({
              id: b.id,
              label: `${b.code} · ${b.name} (${b.available_seats} free)`,
            }))}
            value={target}
            onChange={(value) => {
              setTarget(value);
              setErrors((current) => ({ ...current, target: undefined }));
            }}
            isRequired
            isInvalid={Boolean(errors.target)}
            errorMessage={errors.target}
          />
        )}
        <Textarea
          label="Reason for the transfer"
          value={reason}
          onChange={(value) => {
            setReason(value);
            setErrors((current) => ({ ...current, reason: undefined }));
          }}
          rows={3}
          maxLength={500}
          showCount
          isRequired
          isInvalid={Boolean(errors.reason)}
          errorMessage={errors.reason}
        />
        <div className="flex flex-col-reverse gap-2 pt-2 tablet:flex-row tablet:justify-end">
          <Button variant="secondary" onPress={onClose} isDisabled={pending}>
            Cancel
          </Button>
          <Button
            type="submit"
            isPending={pending}
            isDisabled={!targets || targets.length === 0}
          >
            Transfer student
          </Button>
        </div>
      </Form>
    </div>
  );
}

function RowActions({
  allocation,
  batch,
}: {
  allocation: AllocationWire;
  batch: BatchWire;
}) {
  const mutate = useFinanceMutation("allocation");
  const [transferring, setTransferring] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
  if (allocation.status !== "ACTIVE") return null;

  const withdraw = async (reason: string): Promise<ReasonOutcome> => {
    const outcome = await mutate(
      `/batch-allocations/${allocation.id}/withdraw`,
      { reason, version: allocation.version },
      `${allocation.student.full_name} withdrawn`,
    );
    if (outcome.kind === "done" || outcome.kind === "stale")
      return { kind: "done" };
    if (outcome.kind === "feedback") return outcome;
    return {
      kind: "reason",
      message: "Enter a reason of up to 500 characters.",
    };
  };

  return (
    <PermissionGate permission={BATCH_ALLOCATE}>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" onPress={() => setTransferring(true)}>
          Transfer
        </Button>
        <Button variant="secondary" onPress={() => setWithdrawing(true)}>
          Withdraw
        </Button>
      </div>
      <Dialog
        isOpen={transferring}
        onOpenChange={setTransferring}
        title={`Transfer ${allocation.student.full_name}`}
        description={`From ${batch.code}. The student stays enrolled; this allocation is kept in the history.`}
        size="md"
      >
        {(close) => (
          <TransferForm allocation={allocation} batch={batch} onClose={close} />
        )}
      </Dialog>
      <ReasonDialog
        isOpen={withdrawing}
        onOpenChange={setWithdrawing}
        title={`Withdraw ${allocation.student.full_name} from ${batch.code}?`}
        description="The seat is freed and the admission returns to Admitted. The allocation stays in the history."
        reasonLabel="Reason for the withdrawal"
        confirmLabel="Withdraw student"
        onSubmit={withdraw}
      />
    </PermissionGate>
  );
}

export function AllocationPanel({
  batch,
  allocations,
}: {
  batch: BatchWire;
  allocations: AllocationWire[];
}) {
  const { can } = useTenantSession();
  const [allocating, setAllocating] = useState(false);
  const active = allocations.filter((a) => a.status === "ACTIVE");
  const history = allocations.filter((a) => a.status === "ENDED");
  const canAllocate = batch.status === "OPEN" && batch.available_seats > 0;

  const columns: DataTableColumn<AllocationWire>[] = [
    {
      id: "student",
      header: "Student",
      isRowHeader: true,
      cell: (a) => (
        <span className="flex min-w-0 flex-col">
          <RecordLink href={studentPath(a.student.id)}>
            {a.student.full_name}
          </RecordLink>
          <span className="text-caption text-text-secondary">
            {`${a.student.number} · ${a.admission_number}`}
          </span>
        </span>
      ),
    },
    {
      id: "payment",
      header: "Payment",
      cell: (a) => <PaymentNote allocation={a} />,
    },
    {
      id: "when",
      header: "Allocated",
      visibleFrom: "tablet",
      cell: (a) => (
        <div className="flex flex-col">
          <span>{formatDate(a.allocated_at)}</span>
          <span className="text-caption text-text-secondary">
            {[
              a.allocated_by?.display_name,
              a.transferred_from_batch_code
                ? `from ${a.transferred_from_batch_code}`
                : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </span>
        </div>
      ),
    },
    // Read-only roles get no Actions column (the server refuses the actions anyway).
    ...(can(BATCH_ALLOCATE)
      ? [
          {
            id: "actions",
            header: "Actions",
            cell: (a: AllocationWire) => (
              <RowActions allocation={a} batch={batch} />
            ),
          },
        ]
      : []),
  ];

  const historyColumns: DataTableColumn<AllocationWire>[] = [
    columns[0]!,
    {
      id: "ended",
      header: "Ended",
      cell: (a) => (
        <div className="flex min-w-0 flex-col gap-1">
          <span className="flex flex-wrap items-center gap-2">
            <Badge tone={a.end_reason === "WITHDRAWN" ? "warning" : "info"}>
              {a.end_reason ? END_REASON_LABEL[a.end_reason] : "Ended"}
            </Badge>
            {a.transferred_to_batch_code && (
              <span className="text-caption text-text-secondary">
                {`to ${a.transferred_to_batch_code}`}
              </span>
            )}
          </span>
          <span className="text-caption break-words text-text-secondary">
            {[
              a.ended_at ? formatDate(a.ended_at) : null,
              a.ended_by?.display_name,
              a.end_note ? `“${a.end_note}”` : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </span>
        </div>
      ),
    },
    columns[1]!,
  ];

  return (
    <Card as="section">
      <CardHeader
        title="Students"
        titleAs="h2"
        actions={
          <PermissionGate permission={BATCH_ALLOCATE}>
            <Button
              iconStart={AddIcon}
              onPress={() => setAllocating(true)}
              isDisabled={!canAllocate}
            >
              Allocate student
            </Button>
          </PermissionGate>
        }
      />
      <CardBody>
        {!canAllocate && batch.status === "OPEN" && (
          <Alert tone="info" title="This batch is full">
            Increase the capacity or transfer a student to free a seat.
          </Alert>
        )}
        <Tabs defaultSelectedKey="active">
          <TabList aria-label="Allocations">
            <Tab id="active">{`Allocated (${active.length})`}</Tab>
            <Tab id="history">{`History (${history.length})`}</Tab>
          </TabList>
          <TabPanel id="active">
            <DataTable
              label="Allocated students"
              columns={columns}
              rows={active}
              getRowId={(a) => a.id}
              getRowLabel={(a) => a.student.full_name}
              mobileLayout="cards"
              emptyState={{
                title: "No students allocated yet",
                description:
                  batch.status === "OPEN"
                    ? "Allocate admitted students of this course and campus. Their admission becomes Enrolled."
                    : "Reopen the batch to allocate students.",
              }}
            />
          </TabPanel>
          <TabPanel id="history">
            <DataTable
              label="Allocation history"
              columns={historyColumns}
              rows={history}
              getRowId={(a) => a.id}
              getRowLabel={(a) => a.student.full_name}
              mobileLayout="cards"
              emptyState={{
                title: "No history yet",
                description: "Transfers and withdrawals are kept here.",
              }}
            />
          </TabPanel>
        </Tabs>
      </CardBody>
      {allocating && (
        <AllocateDialog
          batch={batch}
          isOpen={allocating}
          onOpenChange={setAllocating}
        />
      )}
    </Card>
  );
}
