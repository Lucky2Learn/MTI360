import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { FileUpload } from "./FileUpload";

import type { AcceptedFileType } from "./validate-files";

const MB = 1024 * 1024;
const DOCUMENTS: AcceptedFileType[] = [
  { label: "PDF", mimeTypes: ["application/pdf"], extensions: [".pdf"] },
  { label: "JPG", mimeTypes: ["image/jpeg"], extensions: [".jpg", ".jpeg"] },
];

function pdf(name: string, size = 2048, lastModified = 1) {
  const file = new File(["%PDF-1.7"], name, {
    type: "application/pdf",
    lastModified,
  });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

const fileInput = (container: HTMLElement) =>
  container.querySelector<HTMLInputElement>('input[type="file"]')!;

// user-event would otherwise filter files by the input's accept attribute;
// the component's own validation is what is under test.
const setup = () => userEvent.setup({ applyAccept: false });

let createObjectURL: ReturnType<typeof vi.fn>;
beforeEach(() => {
  createObjectURL = vi.fn();
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: createObjectURL,
  });
});
afterEach(() => {
  Reflect.deleteProperty(URL, "createObjectURL");
});

describe("FileUpload", () => {
  it("is a labelled group with a keyboard-operable choose button and passes axe", async () => {
    const { container } = render(
      <FileUpload
        label="Continuous Discharge Certificate (CDC)"
        accept={DOCUMENTS}
        maxSize={5 * MB}
        isRequired
      />,
    );
    expect(
      screen.getByRole("group", { name: /Continuous Discharge Certificate/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Choose file" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("PDF, JPG · up to 5 MB each · 1 file"),
    ).toBeInTheDocument();
    expect(fileInput(container)).toHaveAttribute(
      "accept",
      "application/pdf,.pdf,image/jpeg,.jpg,.jpeg",
    );
    await expectNoA11yViolations(container);
  });

  it("names the drop zone's keyboard/paste button after the field, not an internal default (T00-10)", () => {
    render(
      <FileUpload
        label="Continuous Discharge Certificate (CDC)"
        accept={DOCUMENTS}
        maxSize={5 * MB}
      />,
    );
    expect(
      screen.getByRole("button", {
        name: "Drop or paste files for Continuous Discharge Certificate (CDC)",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /DropZone/ })).toBeNull();
  });

  it("accepts a valid file, lists it and removes it by keyboard", async () => {
    const user = setup();
    const onChange = vi.fn();
    const { container } = render(
      <FileUpload
        label="Passport"
        accept={DOCUMENTS}
        maxSize={5 * MB}
        onChange={onChange}
      />,
    );

    await user.upload(fileInput(container), pdf("passport.pdf"));

    const list = screen.getByRole("list", {
      name: "Selected files for Passport",
    });
    expect(within(list).getByText("passport.pdf")).toBeInTheDocument();
    expect(within(list).getByText("2 KB")).toBeInTheDocument();
    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ name: "passport.pdf" }),
    ]);

    screen.getByRole("button", { name: "Remove passport.pdf" }).focus();
    await user.keyboard("{Enter}");
    expect(onChange).toHaveBeenLastCalledWith([]);
    expect(screen.queryByRole("list", { name: /Selected files/ })).toBeNull();
    await expectNoA11yViolations(container);
  });

  it("rejects disallowed, oversized and extra files with announced text", async () => {
    const user = setup();
    const onReject = vi.fn();
    const { container } = render(
      <FileUpload
        label="Supporting documents"
        accept={DOCUMENTS}
        maxSize={5 * MB}
        maxFiles={2}
        onReject={onReject}
      />,
    );

    await user.upload(fileInput(container), [
      new File(["x"], "setup.exe", { type: "application/x-msdownload" }),
      new File(["x"], "medical.pdf.exe", { type: "application/pdf" }),
      pdf("large.pdf", 6 * MB),
      new File(["x"], "photo.gif", { type: "image/gif" }),
    ]);

    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(
      "setup.exe can't be uploaded because this type of file isn't allowed.",
    );
    expect(status).toHaveTextContent("medical.pdf.exe can't be uploaded");
    expect(status).toHaveTextContent("large.pdf is larger than 5 MB.");
    expect(status).toHaveTextContent(
      "photo.gif isn't an accepted file type. Use PDF or JPG.",
    );
    expect(onReject).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("list", { name: /Selected files/ })).toBeNull();

    await user.upload(fileInput(container), [
      pdf("a.pdf", 10, 1),
      pdf("b.pdf", 10, 2),
      pdf("c.pdf", 10, 3),
    ]);
    expect(
      within(screen.getByRole("list", { name: /Selected files/ })).getAllByRole(
        "listitem",
      ),
    ).toHaveLength(2);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Only 2 files can be added. c.pdf was not added.",
    );
  });

  it("works controlled", async () => {
    const user = setup();
    function Controlled() {
      const [files, setFiles] = useState<File[]>([]);
      return (
        <>
          <FileUpload
            label="Medical certificate"
            accept={DOCUMENTS}
            maxSize={5 * MB}
            value={files}
            onChange={setFiles}
          />
          <output>{files.map((f) => f.name).join(",") || "none"}</output>
        </>
      );
    }
    const { container } = render(<Controlled />);
    await user.upload(fileInput(container), pdf("medical.pdf"));
    expect(
      screen.getByText("medical.pdf", { selector: "output" }),
    ).toBeInTheDocument();
  });

  it("shows an explicit error state with icon and text", () => {
    render(
      <FileUpload
        label="Photo"
        accept={DOCUMENTS}
        maxSize={2 * MB}
        isInvalid
        errorMessage="Upload a recent passport-size photo."
      />,
    );
    expect(screen.getByRole("group", { name: "Photo" })).toBeInTheDocument();
    expect(
      screen.getByText("Upload a recent passport-size photo."),
    ).toBeInTheDocument();
  });

  it("never creates object URLs or previews", async () => {
    const user = setup();
    const { container } = render(
      <FileUpload label="Photo" accept={DOCUMENTS} maxSize={5 * MB} />,
    );
    await user.upload(
      fileInput(container),
      new File(["x"], "photo.jpg", { type: "image/jpeg" }),
    );
    expect(createObjectURL).not.toHaveBeenCalled();
    expect(container.querySelector("img")).toBeNull();
  });

  it("does nothing when disabled", async () => {
    const user = setup();
    const onChange = vi.fn();
    const { container } = render(
      <FileUpload
        label="Photo"
        accept={DOCUMENTS}
        maxSize={5 * MB}
        isDisabled
        onChange={onChange}
      />,
    );
    expect(screen.getByRole("button", { name: "Choose file" })).toBeDisabled();
    await user.upload(fileInput(container), pdf("x.pdf"));
    expect(onChange).not.toHaveBeenCalled();
  });
});
