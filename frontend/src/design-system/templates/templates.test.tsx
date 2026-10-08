import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Badge, Button } from "@/design-system/components";
import { expectHeadingOutline } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { renderScreen } from "@/test/render-screen";

import { DataListTemplate } from "./DataListTemplate";
import { DetailTemplate } from "./DetailTemplate";
import { FormActions, FormCell, FormGrid, FormSection } from "./FormLayout";

// Page templates T02 / T03 and the form layout (Phase 02-1): one h1, the
// side column as a named landmark, DOM order = reading order, accessible in
// Light and Dark.

describe.each(["light", "dark"] as const)("templates (%s)", (theme) => {
  it("T02 Data List: header, toolbar, content and footer in order", async () => {
    const { container } = renderScreen(
      <DataListTemplate
        title="Courses"
        description="The institute catalogue."
        breadcrumbs={[{ label: "Academics" }, { label: "Courses" }]}
        actions={<Button>New course</Button>}
        toolbar={<p>Filters</p>}
        footer={<p>Pages</p>}
      >
        <p>Rows</p>
      </DataListTemplate>,
      { theme },
    );
    expect(
      screen.getByRole("heading", { level: 1, name: "Courses" }),
    ).toBeInTheDocument();
    const text = container.textContent ?? "";
    expect(text.indexOf("Filters")).toBeLessThan(text.indexOf("Rows"));
    expect(text.indexOf("Rows")).toBeLessThan(text.indexOf("Pages"));
    await expectNoA11yViolations(container);
  });

  it("T03 Detail: main, a named side column, then full-width sections", async () => {
    const { container } = renderScreen(
      <DetailTemplate
        title="Arjun Nair"
        status={<Badge tone="info">New</Badge>}
        main={<section aria-label="Enquiry">Enquiry details</section>}
        aside={<p>Follow-ups</p>}
        asideLabel="Lead pipeline"
      >
        <section aria-label="Activity">History</section>
      </DetailTemplate>,
      { theme },
    );
    expect(
      screen.getByRole("complementary", { name: "Lead pipeline" }),
    ).toHaveTextContent("Follow-ups");
    const text = container.textContent ?? "";
    expect(text.indexOf("Enquiry details")).toBeLessThan(
      text.indexOf("Follow-ups"),
    );
    expect(text.indexOf("Follow-ups")).toBeLessThan(text.indexOf("History"));
    expectHeadingOutline(container);
    await expectNoA11yViolations(container);
  });

  it("form layout: titled sections and actions with the primary last", async () => {
    const { container } = renderScreen(
      <form aria-label="Course">
        <FormSection title="Course" description="Basics">
          <FormGrid>
            <FormCell>
              <label>
                Name <input />
              </label>
            </FormCell>
            <FormCell span="full">
              <label>
                Description <textarea />
              </label>
            </FormCell>
          </FormGrid>
        </FormSection>
        <FormActions>
          <Button variant="secondary">Cancel</Button>
          <Button type="submit">Save</Button>
        </FormActions>
      </form>,
      { theme },
    );
    expect(
      screen.getByRole("heading", { level: 2, name: "Course" }),
    ).toBeInTheDocument();
    const buttons = screen.getAllByRole("button").map((b) => b.textContent);
    expect(buttons).toEqual(["Cancel", "Save"]);
    await expectNoA11yViolations(container);
  });
});
