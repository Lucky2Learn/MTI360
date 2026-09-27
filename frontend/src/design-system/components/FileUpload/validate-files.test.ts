import { describe, expect, it } from "vitest";

import {
  DENIED_EXTENSIONS,
  displayName,
  fileExtension,
  formatFileSize,
  validateFiles,
  type AcceptedFileType,
  type FileRules,
} from "./validate-files";

const MB = 1024 * 1024;

const DOCUMENTS: AcceptedFileType[] = [
  { label: "PDF", mimeTypes: ["application/pdf"], extensions: [".pdf"] },
  { label: "JPG", mimeTypes: ["image/jpeg"], extensions: [".jpg", ".jpeg"] },
  { label: "PNG", mimeTypes: ["image/png"], extensions: [".png"] },
];

const RULES: FileRules = { accept: DOCUMENTS, maxSize: 5 * MB, maxFiles: 3 };

function file(name: string, type: string, size = 1024, lastModified = 1): File {
  const blob = new File([new Uint8Array(Math.min(size, 16))], name, {
    type,
    lastModified,
  });
  Object.defineProperty(blob, "size", { value: size });
  return blob;
}

describe("validateFiles (client-side UX checks)", () => {
  it("accepts files whose extension AND MIME type match an accepted entry", () => {
    const result = validateFiles(
      [
        file("cdc.pdf", "application/pdf"),
        file("photo.JPG", "image/jpeg"),
        file("sign.png", "image/png"),
      ],
      [],
      RULES,
    );
    expect(result.accepted.map((f) => f.name)).toEqual([
      "cdc.pdf",
      "photo.JPG",
      "sign.png",
    ]);
    expect(result.rejected).toEqual([]);
  });

  it.each([
    ["wrong extension", file("notes.docx", "application/pdf"), "type"],
    ["wrong MIME type", file("photo.jpg", "application/x-msdownload"), "type"],
    ["missing MIME type", file("scan.pdf", ""), "type"],
    ["no extension", file("passport", "application/pdf"), "type"],
    ["double extension", file("medical.pdf.exe", "application/pdf"), "denied"],
    ["script", file("marks.js", "text/javascript"), "denied"],
    ["svg", file("logo.svg", "image/svg+xml"), "denied"],
    ["html", file("page.html", "text/html"), "denied"],
    [
      "macro document",
      file("fees.xlsm", "application/vnd.ms-excel.sheet.macroEnabled.12"),
      "denied",
    ],
    ["empty file", file("blank.pdf", "application/pdf", 0), "empty"],
    ["oversized file", file("big.pdf", "application/pdf", 5 * MB + 1), "size"],
    ["control characters", file("cdc\u0007.pdf", "application/pdf"), "name"],
    ["path separator", file("..\\cdc.pdf", "application/pdf"), "name"],
    [
      "very long name",
      file(`${"a".repeat(260)}.pdf`, "application/pdf"),
      "name",
    ],
  ])("rejects a %s", (_case, candidate, reason) => {
    const result = validateFiles([candidate], [], RULES);
    expect(result.accepted).toEqual([]);
    expect(result.rejected[0]?.reason).toBe(reason);
    expect(result.rejected[0]?.message.length).toBeGreaterThan(0);
  });

  it("rejects denied types even when accept would allow them", () => {
    const permissive: FileRules = {
      ...RULES,
      accept: [
        {
          label: "Any",
          mimeTypes: ["application/octet-stream"],
          extensions: [".exe"],
        },
      ],
    };
    expect(
      validateFiles(
        [file("setup.exe", "application/octet-stream")],
        [],
        permissive,
      ).rejected[0]?.reason,
    ).toBe("denied");
    expect(DENIED_EXTENSIONS).toEqual(
      expect.arrayContaining([".exe", ".svg", ".html", ".js", ".docm"]),
    );
  });

  it("enforces the maximum number of files across existing and new files", () => {
    const existing = [
      file("a.pdf", "application/pdf", 10, 1),
      file("b.pdf", "application/pdf", 10, 2),
    ];
    const result = validateFiles(
      [
        file("c.pdf", "application/pdf", 10, 3),
        file("d.pdf", "application/pdf", 10, 4),
      ],
      existing,
      RULES,
    );
    expect(result.accepted.map((f) => f.name)).toEqual(["c.pdf"]);
    expect(result.rejected[0]).toMatchObject({ reason: "count" });
    expect(result.rejected[0]?.message).toContain("Only 3 files can be added");
  });

  it("ignores duplicates of already-selected files", () => {
    const existing = [file("cdc.pdf", "application/pdf", 100, 7)];
    const result = validateFiles(
      [file("cdc.pdf", "application/pdf", 100, 7)],
      existing,
      RULES,
    );
    expect(result.rejected[0]?.reason).toBe("duplicate");
  });

  it("writes plain-language messages that name the allowed types and size", () => {
    const type = validateFiles([file("photo.gif", "image/gif")], [], RULES)
      .rejected[0]!;
    expect(type.message).toBe(
      "photo.gif isn't an accepted file type. Use PDF, JPG or PNG.",
    );
    const size = validateFiles(
      [file("big.pdf", "application/pdf", 6 * MB)],
      [],
      RULES,
    ).rejected[0]!;
    expect(size.message).toBe("big.pdf is larger than 5 MB.");
  });
});

describe("file helpers", () => {
  it("extracts the last extension in lower case", () => {
    expect(fileExtension("CDC.Scan.PDF")).toBe(".pdf");
    expect(fileExtension(".env")).toBe("");
    expect(fileExtension("README")).toBe("");
    expect(fileExtension("trailing.")).toBe("");
  });

  it("formats sizes with en-IN digits", () => {
    expect(formatFileSize(512)).toBe("512 bytes");
    expect(formatFileSize(240 * 1024)).toBe("240 KB");
    expect(formatFileSize(5 * MB)).toBe("5 MB");
    expect(formatFileSize(1.5 * MB)).toBe("1.5 MB");
  });

  it("makes names safe for messages", () => {
    expect(displayName("cdc\u0000.pdf")).toBe("cdc?.pdf");
    expect(displayName("x".repeat(100))).toHaveLength(78);
  });
});
