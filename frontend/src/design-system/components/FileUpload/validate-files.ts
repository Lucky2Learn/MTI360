// Client-side file checks for FileUpload (T00-07B, decision D7).
//
// UX ONLY. These checks give fast, understandable feedback and avoid pointless
// uploads. They are NOT a security control: file names, extensions and the
// browser-reported MIME type are all client-controlled. The server remains
// authoritative and must run the full pipeline (CLAUDE.md §50, ARCHITECTURE.md
// §49): extension + sniffed MIME + size validation, filename sanitisation,
// content validation, malware scan, tenant-scoped storage.
//
// Nothing here reads file contents or creates object URLs.

export type AcceptedFileType = {
  /** Short name used in messages, e.g. "PDF". */
  label: string;
  /** Browser-reported MIME types for this entry, e.g. ["application/pdf"]. */
  mimeTypes: string[];
  /** Lower-case extensions including the dot, e.g. [".pdf"]. */
  extensions: string[];
};

export type FileRejectionReason =
  "name" | "denied" | "type" | "empty" | "size" | "duplicate" | "count";

export type FileRejection = {
  file: File;
  reason: FileRejectionReason;
  message: string;
};

export type FileRules = {
  accept: AcceptedFileType[];
  /** Maximum size per file, in bytes. */
  maxSize: number;
  /** Maximum number of files in total (existing + new). */
  maxFiles: number;
  locale?: string;
};

/**
 * Always rejected, even when `accept` would allow them: executables, scripts,
 * installers, active web content and macro-enabled Office formats.
 */
export const DENIED_EXTENSIONS: readonly string[] = [
  ".exe",
  ".msi",
  ".bat",
  ".cmd",
  ".com",
  ".scr",
  ".pif",
  ".cpl",
  ".dll",
  ".sys",
  ".ps1",
  ".psm1",
  ".sh",
  ".bash",
  ".zsh",
  ".js",
  ".mjs",
  ".cjs",
  ".vbs",
  ".vbe",
  ".wsf",
  ".wsh",
  ".hta",
  ".jar",
  ".apk",
  ".app",
  ".dmg",
  ".deb",
  ".rpm",
  ".lnk",
  ".reg",
  ".html",
  ".htm",
  ".xhtml",
  ".svg",
  ".xml",
  ".php",
  ".py",
  ".rb",
  ".pl",
  ".docm",
  ".dotm",
  ".xlsm",
  ".xltm",
  ".xlam",
  ".pptm",
  ".potm",
  ".ppsm",
];

const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f]/;
const PATH_SEPARATORS = /[\\/]/;
const MAX_NAME_LENGTH = 255;

/** Lower-case last extension including the dot, or "" when there is none. */
export function fileExtension(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot > 0 && dot < name.length - 1 ? name.slice(dot).toLowerCase() : "";
}

/** File size for messages, e.g. "5 MB", "240 KB" (binary units, locale digits). */
export function formatFileSize(bytes: number, locale = "en-IN"): string {
  const format = (value: number) =>
    new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(value);
  if (bytes >= 1024 * 1024) return `${format(bytes / (1024 * 1024))} MB`;
  if (bytes >= 1024) return `${format(bytes / 1024)} KB`;
  return `${format(bytes)} bytes`;
}

/** Safe, short name for messages (control characters replaced, truncated). */
export function displayName(name: string): string {
  const cleaned = name.replace(/[\u0000-\u001f\u007f]/g, "?");
  return cleaned.length > 80 ? `${cleaned.slice(0, 77)}…` : cleaned;
}

function joinLabels(labels: string[]): string {
  if (labels.length <= 1) return labels.join("");
  return `${labels.slice(0, -1).join(", ")} or ${labels[labels.length - 1]}`;
}

function sameFile(a: File, b: File): boolean {
  return (
    a.name === b.name && a.size === b.size && a.lastModified === b.lastModified
  );
}

export function validateFiles(
  incoming: File[],
  existing: File[],
  rules: FileRules,
): { accepted: File[]; rejected: FileRejection[] } {
  const accepted: File[] = [];
  const rejected: FileRejection[] = [];
  const allowed = joinLabels(rules.accept.map((type) => type.label));
  const reject = (file: File, reason: FileRejectionReason, message: string) =>
    rejected.push({ file, reason, message });

  for (const file of incoming) {
    const name = displayName(file.name);
    const extension = fileExtension(file.name);
    const mime = file.type.toLowerCase();

    if (
      file.name.length === 0 ||
      file.name.length > MAX_NAME_LENGTH ||
      CONTROL_CHARACTERS.test(file.name) ||
      PATH_SEPARATORS.test(file.name)
    ) {
      reject(
        file,
        "name",
        `"${name}" has a file name that can't be used. Rename the file and try again.`,
      );
    } else if (DENIED_EXTENSIONS.includes(extension)) {
      reject(
        file,
        "denied",
        `${name} can't be uploaded because this type of file isn't allowed.`,
      );
    } else if (
      !rules.accept.some(
        (type) =>
          type.extensions.includes(extension) &&
          type.mimeTypes.map((value) => value.toLowerCase()).includes(mime),
      )
    ) {
      reject(
        file,
        "type",
        `${name} isn't an accepted file type. Use ${allowed}.`,
      );
    } else if (file.size === 0) {
      reject(file, "empty", `${name} is empty.`);
    } else if (file.size > rules.maxSize) {
      reject(
        file,
        "size",
        `${name} is larger than ${formatFileSize(rules.maxSize, rules.locale)}.`,
      );
    } else if (
      [...existing, ...accepted].some((other) => sameFile(other, file))
    ) {
      reject(file, "duplicate", `${name} has already been added.`);
    } else if (existing.length + accepted.length >= rules.maxFiles) {
      reject(
        file,
        "count",
        rules.maxFiles === 1
          ? `Only one file can be added. ${name} was not added.`
          : `Only ${rules.maxFiles} files can be added. ${name} was not added.`,
      );
    } else {
      accepted.push(file);
    }
  }

  return { accepted, rejected };
}
