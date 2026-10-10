"use client";

import { useState } from "react";

import {
  Alert,
  Button,
  Dialog,
  FileUpload,
  Select,
  type AcceptedFileType,
} from "@/design-system/components";
import type { DocumentType, DocumentWire } from "@/lib/api/admissions";
import type { FormFeedback } from "@/lib/authz/action-feedback";

import { DOCUMENT_TYPE_LABEL } from "../applications/labels";
import { useRecordMutation } from "../applications/mutations";

// Upload or replace an application document (Phase 02-2; ADR-0021 §5, §8;
// INC-22). The browser checks type and size for quick feedback only; the API
// validates the extension, MIME type, leading bytes, size and PDF content
// again, and its codes map to fixed copy. The file travels as multipart form
// data through the same-origin proxy; the file name is never put in a URL.

export const ACCEPTED: AcceptedFileType[] = [
  { label: "PDF", mimeTypes: ["application/pdf"], extensions: [".pdf"] },
  { label: "JPEG", mimeTypes: ["image/jpeg"], extensions: [".jpg", ".jpeg"] },
  { label: "PNG", mimeTypes: ["image/png"], extensions: [".png"] },
];
export const MAX_FILE_BYTES = 10 * 1024 * 1024;

const FILE_MESSAGES: Record<string, string> = {
  file_empty: "Choose a file to upload.",
  file_too_large: "Files can be at most 10 MB.",
  file_name_invalid:
    "Give the file a name with a .pdf, .jpg, .jpeg or .png extension.",
  file_type_not_allowed: "Upload a PDF, JPEG or PNG file.",
  file_content_mismatch:
    "The file's content does not match its type. Save it again and retry.",
  pdf_active_content:
    "PDFs with scripts, attachments or actions are not accepted. Print it to PDF and retry.",
  pdf_encrypted:
    "Password-protected PDFs are not accepted. Remove the password and retry.",
  pdf_unreadable: "This PDF could not be checked. Save it again and retry.",
};
const OTHER_MESSAGES: Record<string, string> = {
  documents_closed: "This application no longer takes documents.",
  not_replaceable: "That document can no longer be replaced.",
  type_mismatch: "A replacement keeps the document's type.",
};

export function UploadDocumentDialog({
  applicationId,
  replacing,
  isOpen,
  onOpenChange,
}: {
  applicationId: string;
  replacing?: DocumentWire;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}) {
  const mutate = useRecordMutation("application");
  const [type, setType] = useState<DocumentType | null>(
    replacing?.document_type ?? null,
  );
  const [files, setFiles] = useState<File[]>([]);
  const [errors, setErrors] = useState<{ type?: string; file?: string }>({});
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);

  const upload = async (close: () => void) => {
    const found: typeof errors = {};
    if (!type) found.type = "Choose the document type.";
    const file = files[0];
    if (!file) found.file = "Choose a file to upload.";
    setErrors(found);
    setFeedback(null);
    if (!type || !file) return;
    const form = new FormData();
    form.append("document_type", type);
    if (replacing) form.append("replaces_document_id", replacing.id);
    form.append("file", file, file.name);
    setPending(true);
    const outcome = await mutate(
      `/applications/${applicationId}/documents`,
      form,
      replacing
        ? "Replacement uploaded"
        : `${DOCUMENT_TYPE_LABEL[type]} uploaded`,
    );
    setPending(false);
    if (outcome.kind === "done" || outcome.kind === "stale") {
      close();
      return;
    }
    if (outcome.kind === "fields") {
      const codes = Object.values(outcome.fields);
      const fileCode = codes.find((code) => code in FILE_MESSAGES);
      const other = codes.find((code) => code in OTHER_MESSAGES);
      if (fileCode) setErrors({ file: FILE_MESSAGES[fileCode] });
      else if (other)
        setFeedback({ tone: "error", title: OTHER_MESSAGES[other] ?? "" });
      else
        setFeedback({ tone: "error", title: "The document wasn't uploaded" });
      return;
    }
    setFeedback(outcome.feedback);
  };

  return (
    <Dialog
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title={
        replacing
          ? `Replace ${DOCUMENT_TYPE_LABEL[replacing.document_type]}`
          : "Upload document"
      }
      description={
        replacing
          ? "The earlier file stays in the document history."
          : "PDF, JPEG or PNG, up to 10 MB."
      }
      size="md"
    >
      {(close) => (
        <div className="flex flex-col gap-4">
          {feedback && (
            <Alert tone={feedback.tone} title={feedback.title}>
              {feedback.body}
            </Alert>
          )}
          {!replacing && (
            <Select
              label="Document type"
              options={(Object.keys(DOCUMENT_TYPE_LABEL) as DocumentType[]).map(
                (value) => ({
                  id: value,
                  label: DOCUMENT_TYPE_LABEL[value],
                }),
              )}
              value={type}
              onChange={(value) => {
                setType(value as DocumentType | null);
                setErrors((current) => ({ ...current, type: undefined }));
              }}
              isRequired
              isInvalid={Boolean(errors.type)}
              errorMessage={errors.type}
            />
          )}
          <FileUpload
            label="File"
            description="Scans and photos must be readable. Password-protected PDFs are not accepted."
            accept={ACCEPTED}
            maxSize={MAX_FILE_BYTES}
            value={files}
            onChange={(next) => {
              setFiles(next);
              setErrors((current) => ({ ...current, file: undefined }));
            }}
            isRequired
            isInvalid={Boolean(errors.file)}
            errorMessage={errors.file}
          />
          <div className="flex flex-col-reverse gap-2 pt-2 tablet:flex-row tablet:justify-end">
            <Button variant="secondary" onPress={close} isDisabled={pending}>
              Cancel
            </Button>
            <Button onPress={() => void upload(close)} isPending={pending}>
              {replacing ? "Upload replacement" : "Upload"}
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
