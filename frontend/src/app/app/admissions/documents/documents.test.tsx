import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectHeadingOutline } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import type { ReadResult } from "@/lib/api/server-read";
import type { SessionWire } from "@/lib/api/types";
import {
  ADMISSIONS_COUNSELLOR,
  ADMISSIONS_MANAGER,
  application,
  applicationActivity,
  documentWire,
  IDS,
  ok,
  queueItem,
} from "@/test/admissions-fixtures";
import { apiError, installFetch, jsonResponse } from "@/test/fetch-mock";
import { readySession } from "@/test/session-fixtures";

import { TenantFrame } from "../../tenant-frame";
import ApplicationDetailPage from "../applications/[applicationId]/page";

import DocumentsPage from "./page";

import type { ReactElement } from "react";

vi.setConfig({ testTimeout: 30_000 });

// ADM-09 documents on the application page and the verification queue (Phase
// 02-2; ADR-0021 §5, §8): multipart uploads with the type, client-side type
// and size checks, the API's file codes as fixed copy, verify with a
// confirmation, reject with a reason, replacement, downloads as attachments.

const state = vi.hoisted(() => ({
  session: null as SessionWire | null,
  reads: [] as [string, ReadResult<unknown>][],
  paths: [] as string[],
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/app/admissions/documents",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: state.push,
    replace: state.replace,
    refresh: state.refresh,
  }),
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
  redirect: (url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`);
  },
}));
vi.mock("@/lib/session/server", () => ({
  readTenantSession: () => Promise.resolve(state.session),
  requireReadyTenantSession: (next: string) =>
    state.session
      ? Promise.resolve(state.session)
      : Promise.reject(new Error(`NEXT_REDIRECT /session-ended?next=${next}`)),
}));
vi.mock("@/lib/api/server-read", () => ({
  tenantApiRead: (p: string) => {
    state.paths.push(p);
    const found = state.reads.find(([pattern]) => p.startsWith(pattern));
    return found
      ? Promise.resolve(found[1])
      : Promise.reject(new Error(`unexpected read ${p}`));
  },
}));

beforeEach(() => {
  state.session = readySession({ permissions: ADMISSIONS_MANAGER });
  state.reads = [];
  state.paths = [];
  state.refresh.mockReset();
});

async function show(
  page: Promise<ReactElement>,
  theme: "light" | "dark" = "light",
) {
  const element = await page;
  document.documentElement.dataset.theme = theme;
  return render(
    <ThemeProvider>
      <TenantFrame session={state.session!} showUnreleased={false}>
        {element}
      </TenantFrame>
    </ThemeProvider>,
  );
}

const APP = `/applications/${IDS.application}`;
const detail = () =>
  ApplicationDetailPage({
    params: Promise.resolve({ applicationId: IDS.application }),
  });

function reads(
  overrides: Parameters<typeof application>[0] = {},
  documents = [documentWire()],
) {
  state.reads.unshift(
    [`${APP}/documents`, ok({ items: documents })],
    [`${APP}/activity`, ok([applicationActivity()], 1)],
    [
      APP,
      ok(
        application({
          status: "SUBMITTED",
          editable: false,
          missing_for_submit: [],
          ...overrides,
        }),
      ),
    ],
  );
}

const pdf = () =>
  new File(["%PDF-1.7"], "medical certificate.pdf", {
    type: "application/pdf",
  });

describe("documents of an application", () => {
  it("uploads the file as multipart form data with its type", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `POST ${APP}/documents`,
      jsonResponse(201, { data: documentWire() }),
    );
    reads({}, []);
    await show(detail());
    expect(screen.getByText("No documents yet")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Upload document" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Upload document",
    });
    await user.click(within(dialog).getByRole("button", { name: "Upload" }));
    expect(
      await within(dialog).findByText("Choose the document type."),
    ).toBeInTheDocument();
    await user.click(
      within(dialog).getByRole("button", { name: /Document type/ }),
    );
    await user.click(
      await screen.findByRole("option", { name: "Medical certificate" }),
    );
    await user.upload(
      dialog.querySelector<HTMLInputElement>('input[type="file"]')!,
      pdf(),
    );
    await user.click(within(dialog).getByRole("button", { name: "Upload" }));
    await waitFor(() =>
      expect(api.callsTo(`POST ${APP}/documents`)).toHaveLength(1),
    );
    const call = api.callsTo(`POST ${APP}/documents`)[0]!;
    expect(call.body).toEqual({
      document_type: "MEDICAL_CERTIFICATE",
      file: { file: "medical certificate.pdf", type: "application/pdf" },
    });
    expect(call.headers["content-type"]).toBeUndefined();
    expect(call.headers["x-csrf-token"]).toBeTruthy();
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
  });

  it("refuses other file types in the browser and shows the API's file codes as fixed copy", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `POST ${APP}/documents`,
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "file", code: "pdf_active_content" }],
      }),
      apiError(413, "PAYLOAD_TOO_LARGE"),
    );
    reads({}, []);
    await show(detail());
    await user.click(screen.getByRole("button", { name: "Upload document" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(
      within(dialog).getByRole("button", { name: /Document type/ }),
    );
    await user.click(await screen.findByRole("option", { name: "Passport" }));
    const input = dialog.querySelector<HTMLInputElement>('input[type="file"]')!;
    await userEvent
      .setup({ applyAccept: false })
      .upload(
        input,
        new File(["<html>"], "passport.html", { type: "text/html" }),
      );
    expect(api.callsTo(`POST ${APP}/documents`)).toHaveLength(0);
    await user.upload(input, pdf());
    await user.click(within(dialog).getByRole("button", { name: "Upload" }));
    expect(
      await within(dialog).findByText(
        /PDFs with scripts, attachments or actions are not accepted/,
      ),
    ).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Upload" }));
    expect(
      await within(dialog).findByText("Files can be at most 10 MB."),
    ).toBeInTheDocument();
    expect(within(dialog).queryByText(/SERVER-/)).not.toBeInTheDocument();
  });

  it("verifies after a confirmation and rejects only with a reason", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `POST /documents/${IDS.passport}/verify`,
      jsonResponse(200, { data: documentWire({ status: "VERIFIED" }) }),
    );
    api.on(
      `POST /documents/${IDS.medical}/reject`,
      jsonResponse(200, { data: documentWire({ status: "REJECTED" }) }),
    );
    reads({}, [
      documentWire(),
      documentWire({
        id: IDS.medical,
        document_type: "MEDICAL_CERTIFICATE",
        file_name: "medical.pdf",
      }),
    ]);
    await show(detail());
    const list = screen.getByRole("list", { name: "Current documents" });
    const [passport, medical] = within(list).getAllByRole("listitem");
    await user.click(within(passport!).getByRole("button", { name: "Verify" }));
    const confirm = await screen.findByRole("alertdialog", {
      name: "Verify Passport?",
    });
    await user.click(
      within(confirm).getByRole("button", { name: "Verify document" }),
    );
    await waitFor(() =>
      expect(
        api.callsTo(`POST /documents/${IDS.passport}/verify`),
      ).toHaveLength(1),
    );
    expect(
      api.callsTo(`POST /documents/${IDS.passport}/verify`)[0]!.body,
    ).toEqual({ version: 2 });
    await user.click(within(medical!).getByRole("button", { name: "Reject" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(
      within(dialog).getByRole("button", { name: "Reject document" }),
    );
    expect(
      await within(dialog).findByText("Enter why the document is rejected."),
    ).toBeInTheDocument();
    await user.type(
      within(dialog).getByRole("textbox", { name: /Reason/ }),
      "Medical certificate expired",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Reject document" }),
    );
    await waitFor(() =>
      expect(api.callsTo(`POST /documents/${IDS.medical}/reject`)).toHaveLength(
        1,
      ),
    );
    expect(
      api.callsTo(`POST /documents/${IDS.medical}/reject`)[0]!.body,
    ).toEqual({
      reason: "Medical certificate expired",
      version: 2,
    });
  });

  it("replaces a rejected document and keeps the earlier version in the history", async () => {
    const user = userEvent.setup();
    state.session = readySession({ permissions: ADMISSIONS_COUNSELLOR });
    const api = installFetch();
    api.on(
      `POST ${APP}/documents`,
      jsonResponse(201, { data: documentWire() }),
    );
    reads({ status: "CORRECTION_REQUIRED", editable: true }, [
      documentWire({
        status: "REJECTED",
        rejection_reason: "Scan is unreadable",
        reviewed_by: "Ananya Rao",
        reviewed_at: "2026-10-10T05:00:00Z",
      }),
      documentWire({
        id: "old",
        current: false,
        status: "REJECTED",
        file_name: "first-scan.pdf",
        replaced_at: "2026-10-09T08:00:00Z",
      }),
    ]);
    await show(detail());
    expect(screen.getByText("Reason: Scan is unreadable")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Verify" }),
    ).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Show earlier versions (1)" }),
    );
    expect(
      screen.getByRole("list", { name: "Earlier versions" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Replace" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Replace Passport",
    });
    expect(
      within(dialog).queryByRole("button", { name: /Document type/ }),
    ).not.toBeInTheDocument();
    await user.upload(
      dialog.querySelector<HTMLInputElement>('input[type="file"]')!,
      pdf(),
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Upload replacement" }),
    );
    await waitFor(() =>
      expect(api.callsTo(`POST ${APP}/documents`)).toHaveLength(1),
    );
    expect(api.callsTo(`POST ${APP}/documents`)[0]!.body).toMatchObject({
      document_type: "PASSPORT",
      replaces_document_id: IDS.passport,
    });
  });
});

describe("ADM-09 verification queue", () => {
  const queue = (search: Record<string, string> = {}) =>
    DocumentsPage({ searchParams: Promise.resolve(search) });

  it("needs document.read", async () => {
    state.session = readySession({ permissions: ["application.read"] });
    await show(queue());
    expect(
      screen.getByText("You don't have access to this page"),
    ).toBeInTheDocument();
  });

  it.each(["light", "dark"] as const)(
    "lists documents awaiting verification, oldest first, and passes axe (%s)",
    async (theme) => {
      state.reads.unshift(["/documents", ok([queueItem()], 1)]);
      const { container } = await show(queue(), theme);
      expect(
        screen.getByRole("heading", {
          level: 1,
          name: "Document verification",
        }),
      ).toBeInTheDocument();
      const table = screen.getByRole("table", { name: "Documents" });
      expect(
        within(table).getByRole("link", { name: "Arjun Nair" }),
      ).toHaveAttribute(
        "href",
        `/app/admissions/applications/${IDS.application}`,
      );
      expect(
        within(table).getByRole("link", { name: /arjun-passport\.pdf/ }),
      ).toHaveAttribute("href", `/api/v1/documents/${IDS.passport}/download`);
      const read = state.paths.find((p) => p.startsWith("/documents?")) ?? "";
      expect(new URLSearchParams(read.split("?")[1]).get("status")).toBe(
        "UNDER_REVIEW",
      );
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("forwards a known status only and shows the empty state", async () => {
    state.reads.unshift(["/documents", ok([], 0)]);
    await show(queue({ status: "REJECTED" }));
    const read = state.paths.find((p) => p.startsWith("/documents?")) ?? "";
    expect(new URLSearchParams(read.split("?")[1]).get("status")).toBe(
      "REJECTED",
    );
    expect(screen.getAllByText("Nothing to verify").length).toBeGreaterThan(0);
    state.paths = [];
    await show(queue({ status: "DELETED" }));
    const fallback = state.paths.find((p) => p.startsWith("/documents?")) ?? "";
    expect(new URLSearchParams(fallback.split("?")[1]).get("status")).toBe(
      "UNDER_REVIEW",
    );
  });
});
