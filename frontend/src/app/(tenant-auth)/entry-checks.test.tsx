import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import type { SessionWire } from "@/lib/api/types";
import { INSTITUTES, readySession, sessionIn } from "@/test/session-fixtures";

import LoginPage from "./login/page";
import SelectCampusPage from "./select-campus/page";
import SelectInstitutePage from "./select-institute/page";
import SessionEndedPage from "./session-ended/page";

import type { ReactElement } from "react";

// Server entry checks of the authentication routes (T01-04 UI contract §6).
// They are UX routing only; the API decides every request.

const state = vi.hoisted(() => ({
  session: null as SessionWire | null,
  failure: false,
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/login",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  redirect: (url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`);
  },
}));
vi.mock("@/lib/session/server", () => ({
  readTenantSession: () =>
    state.failure
      ? Promise.reject(new Error("SESSION_READ_FAILED"))
      : Promise.resolve(state.session),
}));

type Params = Record<string, string | string[] | undefined>;
const props = (params: Params = {}) => ({
  searchParams: Promise.resolve(params),
});

async function show(element: Promise<ReactElement>) {
  return render(<ThemeProvider>{await element}</ThemeProvider>);
}

beforeEach(() => {
  state.session = null;
  state.failure = false;
});

describe("/login", () => {
  it("renders sign-in without a session, with an allow-listed notice only", async () => {
    await show(LoginPage(props({ reason: "signed-out" })));
    expect(
      screen.getByRole("heading", { level: 1, name: "Sign in to MTI 360" }),
    ).toBeInTheDocument();
    expect(screen.getByText("You've signed out.")).toBeInTheDocument();
  });

  it("ignores unknown reasons", async () => {
    const { container } = await show(
      LoginPage(props({ reason: "<img src=x>" })),
    );
    expect(container.textContent).not.toContain("img");
    expect(screen.queryByRole("status")).toBeNull();
  });

  it.each([
    [readySession(), "/app/administration/users", "/app/administration/users"],
    [readySession(), "https://evil.example", "/app"],
    [
      sessionIn("institute_selection_required"),
      "/app/administration/users",
      "/select-institute?next=%2Fapp%2Fadministration%2Fusers",
    ],
    [sessionIn("campus_selection_required"), null, "/select-campus"],
  ])(
    "already signed in → the next step (%#)",
    async (session, next, destination) => {
      state.session = session;
      await expect(LoginPage(props(next ? { next } : {}))).rejects.toThrow(
        `NEXT_REDIRECT ${destination}`,
      );
    },
  );

  it("still renders when the session cannot be read", async () => {
    state.failure = true;
    await show(LoginPage(props()));
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });
});

describe("/select-institute", () => {
  it("not signed in → /login (next carried)", async () => {
    await expect(
      SelectInstitutePage(props({ next: "/app/administration/roles" })),
    ).rejects.toThrow(
      "NEXT_REDIRECT /login?next=%2Fapp%2Fadministration%2Froles",
    );
  });

  it("one institute, already active → onwards", async () => {
    state.session = readySession();
    await expect(SelectInstitutePage(props())).rejects.toThrow(
      "NEXT_REDIRECT /app",
    );
  });

  it("renders the chooser for a session without an institute", async () => {
    state.session = sessionIn("institute_selection_required");
    await show(SelectInstitutePage(props()));
    expect(
      screen.getByRole("heading", { level: 1, name: "Choose an institute" }),
    ).toBeInTheDocument();
  });

  it("preselects the active institute when arriving with several", async () => {
    state.session = readySession({
      institutes: [INSTITUTES.coastal, INSTITUTES.harbour],
    });
    await show(SelectInstitutePage(props()));
    expect(screen.getByRole("radio", { name: /Coastal/ })).toBeChecked();
  });

  it("renders 'No institute available' when none remain", async () => {
    state.session = sessionIn("institute_selection_required", {
      institutes: [],
    });
    await show(SelectInstitutePage(props()));
    expect(
      screen.getByRole("heading", { level: 1, name: "No institute available" }),
    ).toBeInTheDocument();
  });
});

describe("/select-campus", () => {
  it("not signed in → /login; no institute → /select-institute; not required → next", async () => {
    await expect(SelectCampusPage(props())).rejects.toThrow(
      "NEXT_REDIRECT /login",
    );
    state.session = sessionIn("institute_selection_required");
    await expect(
      SelectCampusPage(props({ next: "/app/administration/campuses" })),
    ).rejects.toThrow(
      "NEXT_REDIRECT /select-institute?next=%2Fapp%2Fadministration%2Fcampuses",
    );
    state.session = readySession();
    await expect(
      SelectCampusPage(props({ next: "/app/administration/campuses" })),
    ).rejects.toThrow("NEXT_REDIRECT /app/administration/campuses");
  });

  it("renders the chooser, with the notice only for a withdrawn campus", async () => {
    state.session = sessionIn("campus_selection_required");
    const { unmount } = await show(SelectCampusPage(props()));
    expect(
      screen.getByRole("heading", { level: 1, name: "Choose a campus" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/no longer available/)).toBeNull();
    unmount();
    await show(SelectCampusPage(props({ reason: "campus-unavailable" })));
    expect(
      screen.getByText(
        "The campus you were using is no longer available to you. Choose another to continue.",
      ),
    ).toBeInTheDocument();
  });
});

describe("/session-ended", () => {
  it("never redirects, and carries only a valid next to sign-in", async () => {
    state.session = readySession();
    await show(
      SessionEndedPage(props({ reason: "ended", next: "//evil.example" })),
    );
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute(
      "href",
      "/login",
    );
  });
});
