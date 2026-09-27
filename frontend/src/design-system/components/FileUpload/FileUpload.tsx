"use client";

import { useId, useState, type ReactNode } from "react";
import {
  DropZone,
  FileTrigger,
  type FileDropItem,
} from "react-aria-components";

import { Button } from "@/design-system/components/Button";
import { IconButton } from "@/design-system/components/IconButton";
import {
  CloseIcon,
  ErrorIcon,
  FileIcon,
  UploadIcon,
} from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";

import {
  formatFileSize,
  validateFiles,
  type AcceptedFileType,
  type FileRejection,
} from "./validate-files";

// FileUpload (DESIGN-SYSTEM.md §42; CLAUDE.md §50; decision D7).
// Selection and client-side UX validation ONLY: no upload transport, no
// previews, no object URLs, no reading of file contents. The caller uploads
// the selected File objects; the server validates authoritatively.
// Keyboard: "Choose files" button (Enter/Space); the drop zone is focusable
// and supports paste. Rejections are announced politely as text. Each file has
// a labelled remove button.

export type FileUploadProps = {
  label: string;
  description?: ReactNode;
  /** Accepted types (required): MIME + extension must both match an entry. */
  accept: AcceptedFileType[];
  /** Maximum size per file in bytes (required). */
  maxSize: number;
  /** Maximum number of files (default 1). */
  maxFiles?: number;
  /** Selected files (controlled). */
  value?: File[];
  defaultValue?: File[];
  onChange?: (files: File[]) => void;
  onReject?: (rejections: FileRejection[]) => void;
  isRequired?: boolean;
  isDisabled?: boolean;
  isInvalid?: boolean;
  errorMessage?: string;
  locale?: string;
};

export function FileUpload({
  label,
  description,
  accept,
  maxSize,
  maxFiles = 1,
  value,
  defaultValue,
  onChange,
  onReject,
  isRequired = false,
  isDisabled = false,
  isInvalid = false,
  errorMessage,
  locale = "en-IN",
}: FileUploadProps) {
  const labelId = useId();
  const rulesId = useId();
  const descriptionId = useId();
  const errorId = useId();
  const [uncontrolled, setUncontrolled] = useState<File[]>(defaultValue ?? []);
  const [rejections, setRejections] = useState<FileRejection[]>([]);
  const files = value ?? uncontrolled;

  const update = (next: File[]) => {
    if (value === undefined) setUncontrolled(next);
    onChange?.(next);
  };

  const add = (incoming: File[]) => {
    if (isDisabled || incoming.length === 0) return;
    const { accepted, rejected } = validateFiles(incoming, files, {
      accept,
      maxSize,
      maxFiles,
      locale,
    });
    setRejections(rejected);
    if (rejected.length > 0) onReject?.(rejected);
    if (accepted.length > 0) update([...files, ...accepted]);
  };

  const remove = (file: File) => {
    setRejections([]);
    update(files.filter((other) => other !== file));
  };

  const acceptAttribute = [
    ...new Set(
      accept.flatMap((type) => [...type.mimeTypes, ...type.extensions]),
    ),
  ];
  const typeLabels = accept.map((type) => type.label).join(", ");
  const rules = `${typeLabels} · up to ${formatFileSize(maxSize, locale)} each · ${
    maxFiles === 1 ? "1 file" : `up to ${maxFiles} files`
  }`;
  const showError = Boolean(isInvalid && errorMessage);
  const describedBy = cx(
    rulesId,
    description ? descriptionId : undefined,
    showError ? errorId : undefined,
  );

  return (
    <div
      role="group"
      aria-labelledby={labelId}
      className="flex w-full flex-col gap-2"
    >
      <span id={labelId} className="text-body-sm font-medium text-text-primary">
        {label}
        {isRequired && (
          <span aria-hidden="true" className="ml-1 text-error-text">
            *
          </span>
        )}
      </span>
      <DropZone
        isDisabled={isDisabled}
        aria-labelledby={labelId}
        aria-describedby={describedBy}
        onDrop={(event) => {
          const items = event.items.filter(
            (item): item is FileDropItem => item.kind === "file",
          );
          void Promise.all(items.map((item) => item.getFile())).then(add);
        }}
        className={cx(
          "flex flex-col items-center gap-3 rounded-lg border-2 border-dashed bg-surface-primary px-4 py-6 text-center",
          showError ? "border-error" : "border-border-strong",
          "data-drop-target:border-accent-maritime data-drop-target:bg-surface-selected",
          "data-disabled:cursor-not-allowed data-disabled:bg-surface-secondary data-disabled:opacity-50",
          focusRing,
        )}
      >
        <UploadIcon
          aria-hidden="true"
          className="size-6 text-accent-maritime"
        />
        <p className="text-body-sm text-text-secondary pointer-coarse:hidden">
          Drag and drop, or
        </p>
        <FileTrigger
          acceptedFileTypes={acceptAttribute}
          allowsMultiple={maxFiles > 1}
          onSelect={(list) => add(Array.from(list ?? []))}
        >
          <Button
            variant="secondary"
            iconStart={UploadIcon}
            isDisabled={isDisabled}
          >
            {maxFiles > 1 ? "Choose files" : "Choose file"}
          </Button>
        </FileTrigger>
        <p id={rulesId} className="text-caption text-text-secondary">
          {rules}
        </p>
      </DropZone>
      {description && (
        <p id={descriptionId} className="text-caption text-text-secondary">
          {description}
        </p>
      )}
      {showError && (
        <p
          id={errorId}
          className="flex items-start gap-1 text-caption font-medium text-error-text"
        >
          <ErrorIcon aria-hidden="true" className="size-4 shrink-0" />
          <span>{errorMessage}</span>
        </p>
      )}
      <div role="status" aria-live="polite">
        {rejections.length > 0 && (
          <ul className="flex flex-col gap-1">
            {rejections.map((rejection, index) => (
              <li
                key={`${rejection.file.name}-${index}`}
                className="flex items-start gap-1 text-caption font-medium text-error-text"
              >
                <ErrorIcon aria-hidden="true" className="size-4 shrink-0" />
                <span>{rejection.message}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {files.length > 0 && (
        <ul
          aria-label={`Selected files for ${label}`}
          className="flex flex-col gap-2"
        >
          {files.map((file, index) => (
            <li
              key={`${file.name}-${file.size}-${file.lastModified}-${index}`}
              className="flex items-center gap-3 rounded-md border border-border-subtle bg-surface-secondary py-1 pr-1 pl-3"
            >
              <FileIcon
                aria-hidden="true"
                className="size-5 shrink-0 text-text-secondary"
              />
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-body-sm text-text-primary">
                  {file.name}
                </span>
                <span className="text-caption text-text-muted">
                  {formatFileSize(file.size, locale)}
                </span>
              </span>
              <IconButton
                label={`Remove ${file.name}`}
                icon={CloseIcon}
                size="md"
                isDisabled={isDisabled}
                onPress={() => remove(file)}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
