"use client";

import { useState } from "react";

import {
  Alert,
  AlertDialog,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Dialog,
  EmptyState,
  Textarea,
} from "@/design-system/components";
import { AddIcon } from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";
import type { ApplicationStatus, DocumentWire } from "@/lib/api/admissions";
import type { FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import {
  DOCUMENT_STATUS_LABEL,
  DOCUMENT_STATUS_TONE,
  DOCUMENT_TYPE_LABEL,
  DOCUMENT_UPLOAD,
  DOCUMENT_VERIFY,
  downloadPath,
  fileSize,
} from "../applications/labels";
import { useRecordMutation } from "../applications/mutations";
import { formatDateTime } from "../shared/format";

import { UploadDocumentDialog } from "./UploadDocumentDialog";

// ADM-09 documents of one application (Phase 02-2; ADR-0021 §5, §8): the
// current documents with their verification state, download links (always
// downloads, never previews: Y8), verify / reject for verifiers, and upload /
// replace while the application takes documents. Replaced documents stay in
// the history. Every action is decided by the API again.

const OPEN: ApplicationStatus[] = [
  "DRAFT",
  "SUBMITTED",
  "UNDER_REVIEW",
  "CORRECTION_REQUIRED",
];
const FINAL: ApplicationStatus[] = ["ADMITTED", "REJECTED", "NOT_ELIGIBLE"];

export function DownloadLink({
  document,
}: {
  document: Pick<DocumentWire, "id" | "file_name">;
}) {
  return (
    <a
      href={downloadPath(document.id)}
      download
      className={cx(
        "rounded-sm text-body-sm font-medium break-all text-link underline underline-offset-4",
        focusRing,
      )}
    >
      {document.file_name}
      <span className="sr-only"> (download)</span>
    </a>
  );
}

function RejectDialog({
  document,
  onOpenChange,
}: {
  document: DocumentWire;
  onOpenChange: (isOpen: boolean) => void;
}) {
  const mutate = useRecordMutation("document");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);

  const reject = async (close: () => void) => {
    if (!reason.trim()) {
      setError("Enter why the document is rejected.");
      return;
    }
    setPending(true);
    const outcome = await mutate(
      `/documents/${document.id}/reject`,
      { reason: reason.trim(), version: document.version },
      `${DOCUMENT_TYPE_LABEL[document.document_type]} rejected`,
    );
    setPending(false);
    if (outcome.kind === "done" || outcome.kind === "stale") close();
    else if (outcome.kind === "fields") {
      setFeedback({
        tone: "error",
        title: "Only a document awaiting verification is decided.",
      });
    } else setFeedback(outcome.feedback);
  };

  return (
    <Dialog
      isOpen
      onOpenChange={onOpenChange}
      title={`Reject ${DOCUMENT_TYPE_LABEL[document.document_type]}`}
      description="The reason is shown to the team so the applicant can provide a new file."
      size="md"
    >
      {(close) => (
        <div className="flex flex-col gap-4">
          {feedback && <Alert tone={feedback.tone} title={feedback.title} />}
          <Textarea
            label="Reason"
            value={reason}
            onChange={(value) => {
              setReason(value);
              setError(null);
            }}
            description="For example: Medical certificate expired; scan is unreadable."
            maxLength={500}
            showCount
            rows={3}
            isRequired
            isInvalid={Boolean(error)}
            errorMessage={error ?? undefined}
          />
          <div className="flex flex-col-reverse gap-2 pt-2 tablet:flex-row tablet:justify-end">
            <Button variant="secondary" onPress={close} isDisabled={pending}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onPress={() => void reject(close)}
              isPending={pending}
            >
              Reject document
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}

function DocumentItem({
  document,
  status,
  onReplace,
  onReject,
}: {
  document: DocumentWire;
  status: ApplicationStatus;
  onReplace: () => void;
  onReject: () => void;
}) {
  const { can } = useTenantSession();
  const verify = useRecordMutation("document");
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const decidable =
    can(DOCUMENT_VERIFY) &&
    document.status === "UNDER_REVIEW" &&
    !FINAL.includes(status);
  const replaceable =
    can(DOCUMENT_UPLOAD) &&
    document.status !== "VERIFIED" &&
    OPEN.includes(status);

  return (
    <li className="flex min-w-0 flex-col gap-2 border-b border-border-subtle py-4 last:border-b-0">
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <span className="text-body-sm font-medium text-text-primary">
          {DOCUMENT_TYPE_LABEL[document.document_type]}
        </span>
        <Badge tone={DOCUMENT_STATUS_TONE[document.status]}>
          {DOCUMENT_STATUS_LABEL[document.status]}
        </Badge>
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-caption text-text-secondary">
        <DownloadLink document={document} />
        <span>{fileSize(document.size_bytes)}</span>
        <span>
          {`Uploaded ${formatDateTime(document.created_at)}${document.uploaded_by ? ` by ${document.uploaded_by}` : ""}`}
        </span>
        {document.reviewed_by && document.reviewed_at && (
          <span>
            {`${document.status === "VERIFIED" ? "Verified" : "Reviewed"} by ${document.reviewed_by}`}
          </span>
        )}
      </div>
      {document.rejection_reason && (
        <p className="text-body-sm text-text-primary">{`Reason: ${document.rejection_reason}`}</p>
      )}
      {(decidable || replaceable) && (
        <div className="flex flex-wrap gap-2">
          {decidable && (
            <>
              <Button
                size="sm"
                onPress={() => setConfirming(true)}
                isPending={pending}
              >
                Verify
              </Button>
              <Button size="sm" variant="secondary" onPress={onReject}>
                Reject
              </Button>
            </>
          )}
          {replaceable && (
            <Button size="sm" variant="secondary" onPress={onReplace}>
              Replace
            </Button>
          )}
        </div>
      )}
      {confirming && (
        <AlertDialog
          isOpen
          onOpenChange={(open) => !open && setConfirming(false)}
          title={`Verify ${DOCUMENT_TYPE_LABEL[document.document_type]}?`}
          description="Confirm you have checked the file against the original document."
          confirmLabel="Verify document"
          isPending={pending}
          onConfirm={() => {
            setPending(true);
            void verify(
              `/documents/${document.id}/verify`,
              { version: document.version },
              `${DOCUMENT_TYPE_LABEL[document.document_type]} verified`,
            ).finally(() => {
              setPending(false);
              setConfirming(false);
            });
          }}
        />
      )}
    </li>
  );
}

export function DocumentsPanel({
  applicationId,
  status,
  documents,
}: {
  applicationId: string;
  status: ApplicationStatus;
  documents: DocumentWire[];
}) {
  const { can } = useTenantSession();
  const [dialog, setDialog] = useState<
    | { kind: "upload" }
    | { kind: "replace"; document: DocumentWire }
    | { kind: "reject"; document: DocumentWire }
    | null
  >(null);
  const [showHistory, setShowHistory] = useState(false);
  const current = documents.filter((d) => d.current);
  const history = documents.filter((d) => !d.current);
  const uploadable = can(DOCUMENT_UPLOAD) && OPEN.includes(status);
  const close = (open: boolean) => !open && setDialog(null);

  return (
    <Card as="section">
      <CardHeader
        title="Documents"
        titleAs="h2"
        actions={
          uploadable ? (
            <Button
              size="sm"
              iconStart={AddIcon}
              onPress={() => setDialog({ kind: "upload" })}
            >
              Upload document
            </Button>
          ) : undefined
        }
      />
      <CardBody>
        {current.length === 0 ? (
          <EmptyState
            title="No documents yet"
            description={
              uploadable
                ? "Upload the applicant's passport, CDC, marksheets and medical certificate."
                : "Documents uploaded for this application appear here."
            }
          />
        ) : (
          <ul aria-label="Current documents" className="flex flex-col">
            {current.map((document) => (
              <DocumentItem
                key={document.id}
                document={document}
                status={status}
                onReplace={() => setDialog({ kind: "replace", document })}
                onReject={() => setDialog({ kind: "reject", document })}
              />
            ))}
          </ul>
        )}
        {history.length > 0 && (
          <div className="mt-4 flex flex-col gap-2">
            <Button
              variant="ghost"
              size="sm"
              onPress={() => setShowHistory((value) => !value)}
              aria-expanded={showHistory}
            >
              {showHistory
                ? "Hide earlier versions"
                : `Show earlier versions (${history.length})`}
            </Button>
            {showHistory && (
              <ul aria-label="Earlier versions" className="flex flex-col gap-2">
                {history.map((document) => (
                  <li
                    key={document.id}
                    className="flex flex-wrap items-center gap-2 text-caption text-text-secondary"
                  >
                    <span>{DOCUMENT_TYPE_LABEL[document.document_type]}</span>
                    <Badge tone={DOCUMENT_STATUS_TONE[document.status]}>
                      {DOCUMENT_STATUS_LABEL[document.status]}
                    </Badge>
                    <DownloadLink document={document} />
                    {document.rejection_reason && (
                      <span>{`Reason: ${document.rejection_reason}`}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardBody>
      {dialog?.kind === "upload" && (
        <UploadDocumentDialog
          applicationId={applicationId}
          isOpen
          onOpenChange={close}
        />
      )}
      {dialog?.kind === "replace" && (
        <UploadDocumentDialog
          applicationId={applicationId}
          replacing={dialog.document}
          isOpen
          onOpenChange={close}
        />
      )}
      {dialog?.kind === "reject" && (
        <RejectDialog document={dialog.document} onOpenChange={close} />
      )}
    </Card>
  );
}
