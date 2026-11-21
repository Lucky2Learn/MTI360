import { screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { SiteNotFound } from "@/features/enquiry/SiteNotFound";
import { renderScreen } from "@/test/render-screen";

// Branded public 404 of hosted institute pages (Phase 02-4, ADR-0024): the
// institute is named only when the API resolves the request's host (verified,
// active address); otherwise a neutral page. Status 404 comes from notFound()
// in the catch-all route; never staff or platform navigation.

const request = vi.hoisted(() => ({ headers: new Headers() }));
vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({
  headers: () => Promise.resolve(request.headers),
  cookies: () => Promise.resolve({ get: () => undefined }),
}));
vi.mock("@/lib/env", () => ({
  getServerEnv: () => ({
    appEnv: "test",
    apiBaseUrl: "http://api.internal:8000",
    trustedProxyHops: 0,
    publicSiteDomain: "mti360.in",
  }),
}));

const { default: SiteNotFoundPage } = await import("./[site]/not-found");
const { default: SitePathNotFound } =
  await import("./[site]/[...missing]/page");
const { publicSiteRead } = await import("@/lib/api/public-site-read");

const FORM = {
  institute_name: "Konkan Maritime Training Institute",
  courses: [],
  consent: { version: "enquiry-2026-10", text: "…", retention_months: 12 },
  privacy_notice: "…",
};

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  request.headers = new Headers({
    host: "konkan.mti360.in",
    cookie: "__Host-mti360_tsid=staff-session",
    "x-forwarded-host": "victim.mti360.in",
  });
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const respond = (status: number, body: unknown = {}) =>
  fetchMock.mockResolvedValueOnce(
    new Response(JSON.stringify(body), { status }),
  );

const STAFF_NAVIGATION =
  /Dashboard|Admissions|Finance|Tenants|Sign in|Platform/;

describe("publicSiteRead", () => {
  it("forwards only this request's host, never a cookie or a client X-Forwarded-Host", async () => {
    respond(200, { data: FORM });
    const result = await publicSiteRead("/enquiry-form");
    expect(result).toEqual({ kind: "ok", data: FORM });
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://api.internal:8000/api/v1/public/enquiry-form");
    const sent = new Headers(init?.headers);
    expect(sent.get("x-forwarded-host")).toBe("konkan.mti360.in");
    expect(sent.get("cookie")).toBeNull();
  });

  it("maps a 404 to not-found and other failures to an error with the reference", async () => {
    respond(404);
    expect(await publicSiteRead("/enquiry-form")).toEqual({
      kind: "not-found",
    });
    fetchMock.mockResolvedValueOnce(
      new Response("{}", { status: 503, headers: { "x-request-id": "req-9" } }),
    );
    expect(await publicSiteRead("/enquiry-form")).toEqual({
      kind: "error",
      reference: "req-9",
    });
    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    expect(await publicSiteRead("/enquiry-form")).toEqual({
      kind: "error",
      reference: null,
    });
  });
});

describe("public not-found page", () => {
  it("names the institute of a verified address and links to its enquiry page", async () => {
    respond(200, { data: FORM });
    renderScreen(await SiteNotFoundPage());
    expect(
      screen.getByRole("heading", { level: 1, name: "Page not found" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /isn.t available on the Konkan Maritime Training Institute website/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Ask about a course" }),
    ).toHaveAttribute("href", "/enquiry");
    expect(document.body.textContent).not.toMatch(STAFF_NAVIGATION);
  });

  it.each([
    ["an unknown, inactive or unverified address", 404],
    ["an unreachable API", 503],
  ])("reveals no institute for %s", async (_, status) => {
    respond(status);
    const { container } = renderScreen(await SiteNotFoundPage());
    expect(
      screen.getByRole("heading", { level: 1, name: "Page not found" }),
    ).toBeInTheDocument();
    expect(container.textContent).not.toContain("Konkan");
    expect(container.textContent).toContain(
      "This website address isn't available.",
    );
    expect(
      screen.queryByRole("link", { name: "Ask about a course" }),
    ).toBeNull();
    expect(screen.queryByRole("navigation")).toBeNull();
    expect(container.textContent).not.toMatch(STAFF_NAVIGATION);
  });

  it("keeps HTTP 404: every other path of an address calls notFound()", () => {
    let thrown: unknown;
    try {
      SitePathNotFound();
    } catch (error) {
      thrown = error;
    }
    expect(String((thrown as { digest?: string })?.digest)).toMatch(/404/);
  });
});

describe("SiteNotFound view", () => {
  it.each(["light", "dark"] as const)(
    "has no accessibility violations, branded and neutral (%s)",
    async (theme) => {
      const branded = renderScreen(
        <SiteNotFound institute="Konkan Maritime Training Institute" />,
        { theme },
      );
      await expectNoA11yViolations(branded.container);
      branded.unmount();
      const neutral = renderScreen(<SiteNotFound institute={null} />, {
        theme,
      });
      await expectNoA11yViolations(neutral.container);
    },
  );

  it("offers only the site's own navigation when the institute is known", () => {
    renderScreen(
      <SiteNotFound institute="Konkan Maritime Training Institute" />,
    );
    const nav = screen.getByRole("navigation", { name: "Website" });
    expect(
      within(nav)
        .getAllByRole("link")
        .map((link) => link.getAttribute("href")),
    ).toEqual(["/enquiry"]);
  });
});
