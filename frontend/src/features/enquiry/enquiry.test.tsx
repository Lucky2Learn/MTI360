import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import type { EnquiryFormWire } from "@/lib/api/public-enquiry";
import { apiError, installFetch, jsonResponse } from "@/test/fetch-mock";
import { renderScreen } from "@/test/render-screen";

import { EnquiryPage } from "./EnquiryPage";

// Hosted enquiry page (Phase 02-4, ADR-0024): minimal data, mandatory and
// versioned consent, a hidden spam trap, the same confirmation for every
// accepted enquiry, server messages never shown.

vi.setConfig({ testTimeout: 20_000 });

const FORM: EnquiryFormWire = {
  institute_name: "Konkan Maritime Training Institute",
  courses: [
    { id: "c-gpr", name: "GP Rating", category: "PRE_SEA" },
    { id: "c-dns", name: "Diploma in Nautical Science", category: "PRE_SEA" },
  ],
  consent: {
    version: "enquiry-2026-10",
    text: "I agree that Konkan Maritime Training Institute may use the details in this form to answer my enquiry. My details are kept for up to 12 months.",
    retention_months: 12,
  },
  privacy_notice:
    "Konkan Maritime Training Institute receives your enquiry through MTI 360. We keep them for up to 12 months.",
};

const ACCEPTED = () =>
  jsonResponse(202, { data: { status: "received" }, meta: {} });

afterEach(() => {
  vi.unstubAllGlobals();
});

function render(theme: "light" | "dark" = "light") {
  return renderScreen(<EnquiryPage kind="ok" form={FORM} />, { theme });
}

async function fillValid(user: ReturnType<typeof userEvent.setup>) {
  await user.type(
    screen.getByRole("textbox", { name: /^Full name/ }),
    "Ananya Iyer",
  );
  await user.type(
    screen.getByRole("textbox", { name: /^Email/ }),
    "ananya.iyer@example.com",
  );
  await user.click(screen.getByRole("checkbox", { name: /I agree/ }));
}

describe("hosted enquiry page", () => {
  it("shows the institute, its courses, the consent and the privacy notice", async () => {
    render();
    expect(
      screen.getByRole("heading", { level: 1, name: "Ask about a course" }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("Konkan Maritime Training Institute").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("checkbox", { name: /kept for up to 12 months/ }),
    ).not.toBeChecked();
    expect(
      screen.getByText(/We keep them for up to 12 months/),
    ).toBeInTheDocument();
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("button", { name: /Course/ }));
    const listbox = await screen.findByRole("listbox");
    expect(
      within(listbox)
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toEqual(["GP Rating", "Diploma in Nautical Science", "Not sure yet"]);
  });

  it.each(["light", "dark"] as const)(
    "has no accessibility violations (%s)",
    async (theme) => {
      const { container } = render(theme);
      await expectNoA11yViolations(container);
    },
  );

  it("lays out for phones first: email and phone side by side only from tablet", () => {
    render();
    const email = screen.getByRole("textbox", { name: /^Email/ });
    const row = email.closest(".grid");
    expect(row?.className).toContain("tablet:grid-cols-2");
    expect(row?.className).not.toMatch(/(?:^|\s)grid-cols-2/);
  });

  it("checks the form before sending and moves focus to the first problem", async () => {
    const api = installFetch();
    render();
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("button", { name: "Send enquiry" }));
    expect(await screen.findByText("Enter your name.")).toBeInTheDocument();
    expect(
      screen.getByText("Enter an email address or a phone number."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Agree to the consent to send your enquiry."),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: /^Full name/ })).toHaveFocus(),
    );
    expect(screen.getByRole("textbox", { name: /^Full name/ })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(api.calls).toEqual([]);
  });

  it("requires consent even when everything else is valid", async () => {
    const api = installFetch();
    render();
    const user = userEvent.setup({ delay: null });
    await user.type(
      screen.getByRole("textbox", { name: /^Full name/ }),
      "Ananya Iyer",
    );
    await user.type(
      screen.getByRole("textbox", { name: /^Phone/ }),
      "+91 90000 10401",
    );
    await user.click(screen.getByRole("button", { name: "Send enquiry" }));
    expect(
      await screen.findByText("Agree to the consent to send your enquiry."),
    ).toBeInTheDocument();
    expect(api.calls).toEqual([]);
  });

  it("refuses an invalid email or phone number", async () => {
    installFetch();
    render();
    const user = userEvent.setup({ delay: null });
    await user.type(screen.getByRole("textbox", { name: /^Email/ }), "ananya");
    await user.type(screen.getByRole("textbox", { name: /^Phone/ }), "call me");
    await user.click(screen.getByRole("button", { name: "Send enquiry" }));
    expect(
      await screen.findByText("Enter a valid email address."),
    ).toBeInTheDocument();
    expect(screen.getByText("Enter a valid phone number.")).toBeInTheDocument();
  });

  it("keeps the spam trap away from people and assistive technology", () => {
    const { container } = render();
    const trap = container.querySelector<HTMLInputElement>(
      'input[name="website"]',
    );
    expect(trap).not.toBeNull();
    expect(trap).toHaveAttribute("tabindex", "-1");
    expect(trap?.closest('[aria-hidden="true"]')).not.toBeNull();
    expect(screen.queryByRole("textbox", { name: /Website/ })).toBeNull();
  });

  it("sends exactly the entered data with the consent version and confirms", async () => {
    const api = installFetch();
    api.on("POST /public/enquiries", ACCEPTED());
    render();
    const user = userEvent.setup({ delay: null });
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: /Course/ }));
    await user.click(await screen.findByRole("option", { name: "GP Rating" }));
    await user.type(
      screen.getByRole("textbox", { name: /^Message/ }),
      "Next batch dates?",
    );
    await user.click(screen.getByRole("button", { name: "Send enquiry" }));

    const confirmation = await screen.findByText(
      "Thank you, we've received your enquiry",
    );
    expect(confirmation).toBeInTheDocument();
    expect(api.callsTo("POST /public/enquiries")).toHaveLength(1);
    expect(api.callsTo("POST /public/enquiries")[0]!.body).toEqual({
      full_name: "Ananya Iyer",
      email: "ananya.iyer@example.com",
      mobile: null,
      course_id: "c-gpr",
      message: "Next batch dates?",
      consent_accepted: true,
      consent_version: "enquiry-2026-10",
      website: "",
    });
    await user.click(
      screen.getByRole("button", { name: "Send another enquiry" }),
    );
    expect(screen.getByRole("textbox", { name: /^Full name/ })).toHaveValue("");
  });

  it("sends no course for 'Not sure yet'", async () => {
    const api = installFetch();
    api.on("POST /public/enquiries", ACCEPTED());
    render();
    const user = userEvent.setup({ delay: null });
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: /Course/ }));
    await user.click(
      await screen.findByRole("option", { name: "Not sure yet" }),
    );
    await user.click(screen.getByRole("button", { name: "Send enquiry" }));
    await screen.findByText("Thank you, we've received your enquiry");
    expect(api.callsTo("POST /public/enquiries")[0]!.body).toMatchObject({
      course_id: null,
    });
  });

  it("shows the API's field problems in the page's own words", async () => {
    const api = installFetch();
    api.on(
      "POST /public/enquiries",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "course_id", code: "course_not_available" }],
      }),
    );
    render();
    const user = userEvent.setup({ delay: null });
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: "Send enquiry" }));
    expect(
      await screen.findByText("Choose a course from the list."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/SERVER-/)).toBeNull();
  });

  it("asks for a reload when the consent text has changed", async () => {
    const api = installFetch();
    api.on(
      "POST /public/enquiries",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "consent_version", code: "consent_outdated" }],
      }),
    );
    render();
    const user = userEvent.setup({ delay: null });
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: "Send enquiry" }));
    expect(
      await screen.findByText("The consent text has changed"),
    ).toBeInTheDocument();
  });

  it("explains a rate limit with the waiting time", async () => {
    const api = installFetch();
    api.on(
      "POST /public/enquiries",
      apiError(429, "RATE_LIMITED", { headers: { "Retry-After": "300" } }),
    );
    render();
    const user = userEvent.setup({ delay: null });
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: "Send enquiry" }));
    expect(await screen.findByText("Too many enquiries")).toBeInTheDocument();
    expect(
      screen.getByText("Please wait 5 minutes and try again."),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /^Full name/ })).toHaveValue(
      "Ananya Iyer",
    );
  });

  it("keeps the entries when the service fails", async () => {
    const api = installFetch();
    api.on("POST /public/enquiries", apiError(500, "INTERNAL_ERROR"));
    render();
    const user = userEvent.setup({ delay: null });
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: "Send enquiry" }));
    expect(
      await screen.findByText("Your enquiry wasn't sent"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/SERVER-/)).toBeNull();
    expect(screen.getByRole("textbox", { name: /^Email/ })).toHaveValue(
      "ananya.iyer@example.com",
    );
  });

  it("shows an error state when the page content cannot be loaded", () => {
    renderScreen(<EnquiryPage kind="error" reference="req-123" />);
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "The enquiry page couldn't be loaded",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/req-123/)).toBeInTheDocument();
  });
});
