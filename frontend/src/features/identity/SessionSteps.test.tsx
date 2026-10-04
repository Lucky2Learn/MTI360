import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { apiError, installFetch, noContent, ok } from "@/test/fetch-mock";
import { renderScreen } from "@/test/render-screen";
import {
  CAMPUSES,
  INSTITUTES,
  readySession,
  sessionIn,
} from "@/test/session-fixtures";

import { SelectCampusScreen } from "./SelectCampusScreen";
import { SelectInstituteScreen } from "./SelectInstituteScreen";
import { SessionEndedScreen } from "./SessionEndedScreen";

// Whole flows typed key by key through React Aria: allow for a loaded CI host.
vi.setConfig({ testTimeout: 20_000 });

// AUTH-07 Choose institute, AUTH-08 Choose campus and AUTH-05 Session ended
// (T01-04 UI contract §8.5-§8.7), including the T01-08 suspended / revoked
// membership landing (T01-05 §10 rows D-F).

const navigation = vi.hoisted(() => ({
  assignLocation: vi.fn<(url: string) => void>(),
  reloadDocument: vi.fn(),
  currentPath: vi.fn(() => "/select-institute"),
}));
vi.mock("@/lib/session/document", () => navigation);

beforeEach(() => {
  navigation.assignLocation.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const choosing = () => sessionIn("institute_selection_required");
const options = (group: "Institutes" | "Campuses") =>
  within(screen.getByRole("radiogroup", { name: group })).getAllByRole("radio");

describe("AUTH-07 choose institute", () => {
  it("offers exactly the server's institutes, sorted, with the Trial flag", () => {
    renderScreen(<SelectInstituteScreen session={choosing()} next={null} />);
    const radios = options("Institutes");
    expect(radios.map((radio) => radio.getAttribute("value"))).toEqual([
      INSTITUTES.coastal.id,
      INSTITUTES.harbour.id,
    ]);
    expect(screen.getByText("Trial")).toBeInTheDocument();
    expect(
      screen.getByRole("radiogroup", { name: "Institutes" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(`Signed in as ${readySession().user.email}`),
    ).toBeInTheDocument();
  });

  it("switches through PUT /session/tenant with the CSRF token and follows next", async () => {
    const api = installFetch();
    api.on(
      "PUT /session/tenant",
      ok(readySession({ active_institute: INSTITUTES.harbour })),
    );
    renderScreen(
      <SelectInstituteScreen
        session={choosing()}
        next="/app/administration/users"
      />,
    );
    const user = userEvent.setup({ delay: null });
    await user.click(
      screen.getByRole("radio", { name: /Harbour Nautical Academy/ }),
    );
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() =>
      expect(navigation.assignLocation).toHaveBeenCalledWith(
        "/app/administration/users",
      ),
    );
    expect(api.calls[0]).toMatchObject({
      method: "PUT",
      path: "/session/tenant",
      body: { tenant_id: INSTITUTES.harbour.id },
      headers: { "x-csrf-token": "csrf-token-for-tests-only" },
    });
  });

  it("continues to the campus step when the server requires it", async () => {
    const api = installFetch();
    api.on("PUT /session/tenant", ok(sessionIn("campus_selection_required")));
    renderScreen(<SelectInstituteScreen session={choosing()} next={null} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("radio", { name: /Coastal/ }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() =>
      expect(navigation.assignLocation).toHaveBeenCalledWith("/select-campus"),
    );
  });

  it("requires a choice", async () => {
    const api = installFetch();
    renderScreen(<SelectInstituteScreen session={choosing()} next={null} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(
      await screen.findByText("Choose an institute to continue."),
    ).toBeInTheDocument();
    expect(api.fetchMock).not.toHaveBeenCalled();
  });

  it("a forged or withdrawn choice (404): warning and the refreshed list", async () => {
    const api = installFetch();
    api.on("PUT /session/tenant", apiError(404, "NOT_FOUND"));
    api.on(
      "GET /session",
      ok(
        sessionIn("institute_selection_required", {
          institutes: [INSTITUTES.coastal],
        }),
      ),
    );
    renderScreen(<SelectInstituteScreen session={choosing()} next={null} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("radio", { name: /Harbour/ }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(
      await screen.findByText("That institute is no longer available to you."),
    ).toBeInTheDocument();
    await waitFor(() => expect(options("Institutes")).toHaveLength(1));
    expect(screen.queryByRole("radio", { name: /Harbour/ })).toBeNull();
  });

  it("no institute left (membership suspended or revoked): 'No institute available' with Sign out", async () => {
    const api = installFetch();
    api.on("POST /auth/logout", noContent());
    const { container } = renderScreen(
      <SelectInstituteScreen
        session={sessionIn("institute_selection_required", { institutes: [] })}
        next={null}
      />,
    );
    expect(
      screen.getByRole("heading", { level: 1, name: "No institute available" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Your account isn't active in any institute right now. Contact your institute administrator.",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    await expectNoA11yViolations(container);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() =>
      expect(navigation.assignLocation).toHaveBeenCalledWith(
        "/session-ended?reason=signed-out",
      ),
    );
  });

  it("the last institute disappearing on switch shows the empty state", async () => {
    const api = installFetch();
    api.on("PUT /session/tenant", apiError(404, "NOT_FOUND"));
    api.on(
      "GET /session",
      ok(sessionIn("institute_selection_required", { institutes: [] })),
    );
    renderScreen(
      <SelectInstituteScreen
        session={sessionIn("institute_selection_required", {
          institutes: [INSTITUTES.coastal],
        })}
        next={null}
      />,
    );
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("radio", { name: /Coastal/ }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "No institute available",
      }),
    ).toBeInTheDocument();
  });

  it("401 → /session-ended", async () => {
    const api = installFetch();
    api.on("PUT /session/tenant", apiError(401, "AUTHENTICATION_REQUIRED"));
    renderScreen(<SelectInstituteScreen session={choosing()} next={null} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("radio", { name: /Coastal/ }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() =>
      expect(navigation.assignLocation).toHaveBeenCalledWith(
        "/session-ended?reason=ended",
      ),
    );
  });

  it("searches when there are more than 8 institutes", async () => {
    const many = Array.from({ length: 10 }, (_, index) => ({
      id: `00000000-0000-4000-8000-00000000000${index}`,
      name: `Maritime Institute ${String.fromCharCode(65 + index)}`,
      is_trial: false,
    }));
    renderScreen(
      <SelectInstituteScreen
        session={sessionIn("institute_selection_required", {
          institutes: many,
        })}
        next={null}
      />,
    );
    const user = userEvent.setup({ delay: null });
    await user.type(
      screen.getByRole("searchbox", { name: "Find an institute" }),
      "zzz",
    );
    expect(screen.getByText("No institutes match 'zzz'.")).toBeInTheDocument();
    // The chooser's own action (the search field has its clear button too).
    await user.click(
      screen.getAllByRole("button", { name: "Clear search" }).at(-1)!,
    );
    expect(options("Institutes")).toHaveLength(10);
  });

  it("passes axe in Light and Dark", async () => {
    const { container } = renderScreen(
      <SelectInstituteScreen session={choosing()} next={null} />,
      { theme: "dark" },
    );
    await expectNoA11yViolations(container);
  });
});

describe("AUTH-08 choose campus", () => {
  const campusStep = () => sessionIn("campus_selection_required");

  it("offers exactly campus_options with codes, no 'All campuses' and no preselection", () => {
    renderScreen(
      <SelectCampusScreen
        session={campusStep()}
        next={null}
        campusWithdrawn={false}
      />,
    );
    const radios = options("Campuses");
    expect(radios.map((radio) => radio.getAttribute("value"))).toEqual([
      CAMPUSES.kochi.id,
      CAMPUSES.vizag.id,
    ]);
    expect(radios.every((radio) => !(radio as HTMLInputElement).checked)).toBe(
      true,
    );
    expect(screen.queryByText("All campuses")).toBeNull();
    expect(screen.getByText("KOC")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Coastal Maritime Training Institute. You can change campus later from the top bar.",
      ),
    ).toBeInTheDocument();
  });

  it("selects through PUT /session/campus and continues to next", async () => {
    const api = installFetch();
    api.on(
      "PUT /session/campus",
      ok(readySession({ active_campus: CAMPUSES.vizag })),
    );
    renderScreen(
      <SelectCampusScreen
        session={campusStep()}
        next="/app/administration/campuses"
        campusWithdrawn={false}
      />,
    );
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("radio", { name: /Visakhapatnam/ }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() =>
      expect(navigation.assignLocation).toHaveBeenCalledWith(
        "/app/administration/campuses",
      ),
    );
    expect(api.calls[0]).toMatchObject({
      body: { campus_id: CAMPUSES.vizag.id },
      headers: { "x-csrf-token": "csrf-token-for-tests-only" },
    });
  });

  it("a withdrawn campus (404): warning, the session is re-read and the options replaced", async () => {
    const api = installFetch();
    api.on("PUT /session/campus", apiError(404, "NOT_FOUND"));
    api.on(
      "GET /session",
      ok(
        sessionIn("campus_selection_required", {
          campus_options: [
            CAMPUSES.kochi,
            {
              id: "c3f1c2d4-5b6e-4f70-8a9b-0c1d2e3f4a33",
              name: "Mumbai Port Campus",
              code: "BOM",
            },
          ],
        }),
      ),
    );
    renderScreen(
      <SelectCampusScreen
        session={campusStep()}
        next={null}
        campusWithdrawn={false}
      />,
    );
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("radio", { name: /Visakhapatnam/ }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(
      await screen.findByText("That campus is no longer available to you."),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("radio", { name: /Mumbai Port/ }),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByRole("radio", { name: /Visakhapatnam/ })).toBeNull();
  });

  it("shows the withdrawn-campus notice when sent from the application", () => {
    renderScreen(
      <SelectCampusScreen session={campusStep()} next={null} campusWithdrawn />,
    );
    expect(
      screen.getByText(
        "The campus you were using is no longer available to you. Choose another to continue.",
      ),
    ).toBeInTheDocument();
  });

  it("offers 'Choose a different institute' only with two or more institutes", () => {
    const { unmount } = renderScreen(
      <SelectCampusScreen
        session={campusStep()}
        next={null}
        campusWithdrawn={false}
      />,
    );
    expect(
      screen.queryByRole("link", { name: "Choose a different institute" }),
    ).toBeNull();
    unmount();
    renderScreen(
      <SelectCampusScreen
        session={sessionIn("campus_selection_required", {
          institutes: [INSTITUTES.coastal, INSTITUTES.harbour],
        })}
        next="/app/administration/users"
        campusWithdrawn={false}
      />,
    );
    expect(
      screen.getByRole("link", { name: "Choose a different institute" }),
    ).toHaveAttribute(
      "href",
      "/select-institute?next=%2Fapp%2Fadministration%2Fusers",
    );
  });

  it("passes axe in Light and Dark", async () => {
    const { container } = renderScreen(
      <SelectCampusScreen session={campusStep()} next={null} campusWithdrawn />,
    );
    await expectNoA11yViolations(container);
    document.documentElement.dataset.theme = "dark";
    await expectNoA11yViolations(container);
  });
});

describe("AUTH-05 session ended", () => {
  it.each([
    ["ended", "Your session has ended"],
    ["signed-out", "You've signed out"],
  ] as const)(
    "%s: one h1 and a Sign in link carrying next",
    async (reason, title) => {
      const { container } = renderScreen(
        <SessionEndedScreen reason={reason} next="/app/administration/roles" />,
      );
      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        title,
      );
      expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute(
        "href",
        "/login?next=%2Fapp%2Fadministration%2Froles",
      );
      expect(navigation.assignLocation).not.toHaveBeenCalled();
      await expectNoA11yViolations(container);
    },
  );

  it("never distinguishes expiry from revocation", () => {
    const { container } = renderScreen(
      <SessionEndedScreen reason="ended" next={null} />,
    );
    expect(container.textContent).not.toMatch(
      /revoked|expired|suspended|removed/i,
    );
  });
});
