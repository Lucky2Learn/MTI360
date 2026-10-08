import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectHeadingOutline } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import type { ReadResult } from "@/lib/api/server-read";
import type { SessionWire } from "@/lib/api/types";
import { course, IDS, ok } from "@/test/admissions-fixtures";
import { apiError, installFetch, jsonResponse } from "@/test/fetch-mock";
import { readySession } from "@/test/session-fixtures";

import { TenantFrame } from "../../tenant-frame";

import EditCoursePage from "./[courseId]/edit/page";
import CourseDetailPage from "./[courseId]/page";
import NewCoursePage from "./new/page";
import CoursesPage from "./page";

import type { ReactElement } from "react";

vi.setConfig({ testTimeout: 30_000 });

// ACA-01/02/03 (Phase 02-1; blueprint §21): server gate, catalogue states,
// course.manage-only actions, form validation and API error mapping.

const state = vi.hoisted(() => ({
  session: null as SessionWire | null,
  reads: new Map<string, ReadResult<unknown>>(),
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  search: "",
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/app/academics/courses",
  useSearchParams: () => new URLSearchParams(state.search),
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
  tenantApiRead: (path: string) => {
    for (const [prefix, result] of state.reads) {
      if (path.startsWith(prefix)) return Promise.resolve(result);
    }
    return Promise.reject(new Error(`unexpected read ${path}`));
  },
}));

beforeEach(() => {
  state.session = readySession({
    permissions: ["course.read", "course.manage"],
    all_campuses_allowed: true,
  });
  state.reads.clear();
  state.push.mockReset();
  state.replace.mockReset();
  state.refresh.mockReset();
  state.search = "";
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

const list = () => CoursesPage({ searchParams: Promise.resolve({}) });
const detail = (id: string = IDS.gpr) =>
  CourseDetailPage({ params: Promise.resolve({ courseId: id }) });

describe("ACA-01 Courses", () => {
  it("needs a session first, then course.read (AUTHZ-01 at the same URL)", async () => {
    state.session = null;
    await expect(list()).rejects.toThrow(
      "NEXT_REDIRECT /session-ended?next=/app/academics/courses",
    );
    state.session = readySession({ permissions: ["lead.read"] });
    await show(list());
    expect(
      screen.getByRole("heading", {
        name: "You don't have access to this page",
      }),
    ).toBeInTheDocument();
  });

  it.each(["light", "dark"] as const)(
    "lists the catalogue with status and category, and passes axe (%s)",
    async (theme) => {
      state.reads.set(
        "/courses",
        ok(
          [
            course(),
            course({
              id: IDS.dns,
              code: "DNS",
              name: "Diploma in Nautical Science",
              status: "DRAFT",
              duration_value: 1,
              duration_unit: "YEARS",
            }),
          ],
          2,
        ),
      );
      const { container } = await show(list(), theme);
      expect(
        screen.getByRole("heading", { level: 1, name: "Courses" }),
      ).toBeInTheDocument();
      const table = screen.getByRole("table", { name: "Courses" });
      expect(
        within(table).getByRole("link", { name: "GP Rating" }),
      ).toHaveAttribute("href", `/app/academics/courses/${IDS.gpr}`);
      expect(within(table).getByText("6 months")).toBeInTheDocument();
      expect(within(table).getByText("Draft")).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "New course" }),
      ).toBeInTheDocument();
      expectHeadingOutline(container);
      await expectNoA11yViolations(container);
    },
  );

  it("counsellors read the catalogue without management controls", async () => {
    state.session = readySession({ permissions: ["course.read"] });
    state.reads.set("/courses", ok([], 0));
    await show(list());
    expect(screen.queryByRole("link", { name: "New course" })).toBeNull();
    expect(
      screen.getAllByText(
        "Courses appear here once your institute adds them.",
      )[0],
    ).toBeInTheDocument();
  });

  it("managers get a first-course call to action; filters show a filtered-empty state", async () => {
    state.reads.set("/courses", ok([], 0));
    await show(list());
    expect(
      screen.getAllByText(/Create your first course/)[0],
    ).toBeInTheDocument();
    state.search = "status=ARCHIVED";
    await show(list());
    expect(
      screen.getAllByText("No courses match these filters")[0],
    ).toBeInTheDocument();
  });

  it("filters change the URL, never the data directly", async () => {
    const user = userEvent.setup();
    state.reads.set("/courses", ok([course()], 1));
    await show(list());
    await user.click(screen.getAllByRole("button", { name: /Status/ })[0]!);
    await user.click(await screen.findByRole("option", { name: "Archived" }));
    expect(state.replace).toHaveBeenCalledWith(
      "/app/academics/courses?status=ARCHIVED",
      { scroll: false },
    );
  });

  it("a failed read shows the error state with the reference, never server text", async () => {
    state.reads.set("/courses", { kind: "error", reference: "req-7" });
    await show(list());
    expect(screen.getByText("Courses couldn't be loaded")).toBeInTheDocument();
    expect(screen.getByText(/req-7/)).toBeInTheDocument();
  });
});

describe("ACA-02 Course detail", () => {
  it("shows the course and lifecycle actions for managers", async () => {
    state.reads.set(`/courses/${IDS.gpr}`, ok(course()));
    const { container } = await show(detail());
    expect(
      screen.getByRole("heading", { level: 1, name: "GP Rating" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Archive" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Edit" })).toHaveAttribute(
      "href",
      `/app/academics/courses/${IDS.gpr}/edit`,
    );
    await expectNoA11yViolations(container);
  });

  it("archiving asks first, then calls the status endpoint with the version", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      `POST /courses/${IDS.gpr}/status`,
      jsonResponse(200, { data: course({ status: "ARCHIVED" }) }),
    );
    state.reads.set(`/courses/${IDS.gpr}`, ok(course()));
    await show(detail());
    await user.click(screen.getByRole("button", { name: "Archive" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("Leads and applications keep this course");
    await user.click(
      within(dialog).getByRole("button", { name: "Archive course" }),
    );
    await waitFor(() => expect(state.refresh).toHaveBeenCalled());
    expect(api.callsTo(`POST /courses/${IDS.gpr}/status`)[0]!.body).toEqual({
      status: "ARCHIVED",
      version: 2,
    });
  });

  it("counsellors see no actions; another institute's or a malformed ID is not found", async () => {
    state.session = readySession({ permissions: ["course.read"] });
    state.reads.set(`/courses/${IDS.gpr}`, ok(course({ status: "ARCHIVED" })));
    await show(detail());
    expect(screen.queryByRole("button", { name: "Reactivate" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Edit" })).toBeNull();
    state.reads.set(`/courses/${IDS.dns}`, { kind: "not-found" });
    await expect(detail(IDS.dns)).rejects.toThrow("NEXT_NOT_FOUND");
    await expect(detail("../../platform")).rejects.toThrow("NEXT_NOT_FOUND");
  });
});

describe("ACA-03 Create / edit course", () => {
  it("course.manage only", async () => {
    state.session = readySession({ permissions: ["course.read"] });
    await show(NewCoursePage());
    expect(
      screen.getByText("You don't have access to this page"),
    ).toBeInTheDocument();
  });

  it("validates, upper-cases the code and maps a taken code to the field", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on("POST /courses", apiError(409, "CONFLICT"));
    const { container } = await show(NewCoursePage());
    await user.click(screen.getByRole("button", { name: "Create course" }));
    expect(
      await screen.findByText("Enter the course name."),
    ).toBeInTheDocument();
    expect(screen.getByText("Choose a category.")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: /Code/ })).toHaveFocus(),
    );

    await user.type(screen.getByRole("textbox", { name: /Code/ }), "stcw-bst");
    await user.type(
      screen.getByRole("textbox", { name: /Name/ }),
      "STCW Basic Safety Training",
    );
    await user.click(screen.getByRole("button", { name: /Category/ }));
    await user.click(await screen.findByRole("option", { name: "Post-sea" }));
    await user.type(screen.getByRole("textbox", { name: /Duration/ }), "5");
    await user.click(screen.getByRole("button", { name: "Create course" }));
    expect(
      await screen.findByText(/Enter a duration from 1 to 1000 with its unit/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Unit/ }));
    await user.click(await screen.findByRole("option", { name: "Days" }));
    await user.click(screen.getByRole("button", { name: "Create course" }));
    expect(
      await screen.findByText("A course with this code already exists."),
    ).toBeInTheDocument();
    expect(api.callsTo("POST /courses")[0]!.body).toEqual({
      code: "STCW-BST",
      name: "STCW Basic Safety Training",
      category: "POST_SEA",
      duration_value: 5,
      duration_unit: "DAYS",
      eligibility_summary: null,
      description: null,
    });
    expect(container.textContent).not.toContain("SERVER-MESSAGE");
    await expectNoA11yViolations(container);
  });

  it("edits with the code read-only and the loaded version; a conflict is explained", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(`PATCH /courses/${IDS.gpr}`, apiError(409, "CONFLICT"));
    state.reads.set(`/courses/${IDS.gpr}`, ok(course()));
    await show(
      EditCoursePage({ params: Promise.resolve({ courseId: IDS.gpr }) }),
    );
    expect(screen.queryByRole("textbox", { name: /Code/ })).toBeNull();
    expect(screen.getByText("The code can't be changed.")).toBeInTheDocument();
    await user.clear(screen.getByRole("textbox", { name: /Name/ }));
    await user.type(
      screen.getByRole("textbox", { name: /Name/ }),
      "General Purpose Rating",
    );
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(
      await screen.findByText("This was changed by someone else"),
    ).toBeInTheDocument();
    expect(api.callsTo(`PATCH /courses/${IDS.gpr}`)[0]!.body).toMatchObject({
      name: "General Purpose Rating",
      version: 2,
    });
    expect(
      api.callsTo(`PATCH /courses/${IDS.gpr}`)[0]!.body,
    ).not.toHaveProperty("code");
  });
});
