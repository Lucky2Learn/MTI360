import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Form } from "@/design-system/components/Field";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Select } from "./Select";

const COURSES = [
  {
    id: "dns",
    label: "DNS — Diploma in Nautical Science",
    description: "Pre-sea · 1 year",
  },
  {
    id: "gme",
    label: "GME — Graduate Marine Engineering",
    description: "Pre-sea · 1 year",
  },
  {
    id: "bsc",
    label: "B.Sc. Nautical Science",
    description: "Pre-sea · 3 years",
  },
  { id: "eto", label: "ETO — Electro-Technical Officer", isDisabled: true },
];

describe("Select", () => {
  it("renders a labelled trigger with a placeholder and passes axe", async () => {
    const { container } = render(<Select label="Course" options={COURSES} />);
    const trigger = screen.getByRole("button", { name: /Course/ });
    expect(trigger).toHaveTextContent("Select an option");
    await expectNoA11yViolations(container);
  });

  it("opens with the keyboard, moves, selects and returns focus", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Select label="Course" options={COURSES} onChange={onChange} />);

    await user.tab();
    await user.keyboard("{ArrowDown}");
    const listbox = screen.getByRole("listbox");
    expect(within(listbox).getAllByRole("option")).toHaveLength(4);
    await expectNoA11yViolations(document.body);

    await user.keyboard("{ArrowDown}{Enter}");

    expect(onChange).toHaveBeenLastCalledWith("gme");
    expect(screen.queryByRole("listbox")).toBeNull();
    const trigger = screen.getByRole("button", { name: /Course/ });
    // React Aria restores focus asynchronously after the popover closes.
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(trigger).toHaveTextContent("GME — Graduate Marine Engineering");
  });

  it("supports type-ahead and Escape", async () => {
    const user = userEvent.setup();
    render(<Select label="Course" options={COURSES} />);
    await user.tab();
    await user.keyboard("{Enter}");
    await user.keyboard("b");
    expect(
      screen.getByRole("option", { name: /B\.Sc\. Nautical Science/ }),
    ).toHaveAttribute("data-focused", "true");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).toBeNull();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Course/ })).toHaveFocus(),
    );
  });

  it("marks disabled options and does not select them", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Select label="Course" options={COURSES} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /Course/ }));
    const eto = screen.getByRole("option", { name: /ETO/ });
    expect(eto).toHaveAttribute("aria-disabled", "true");
    await user.click(eto);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("works controlled", async () => {
    const user = userEvent.setup();
    function Controlled() {
      const [value, setValue] = useState<string | null>("dns");
      return (
        <>
          <Select
            label="Course"
            options={COURSES}
            value={value}
            onChange={setValue}
          />
          <output>{value ?? "none"}</output>
        </>
      );
    }
    render(<Controlled />);
    expect(screen.getByRole("button", { name: /Course/ })).toHaveTextContent(
      "DNS",
    );
    await user.click(screen.getByRole("button", { name: /Course/ }));
    await user.click(screen.getByRole("option", { name: /B\.Sc/ }));
    expect(screen.getByText("bsc")).toBeInTheDocument();
  });

  it("is required and submits the selected id under its name", async () => {
    const user = userEvent.setup();
    let submitted: FormData | undefined;
    render(
      <Form
        onSubmit={(event) => {
          event.preventDefault();
          submitted = new FormData(event.currentTarget);
        }}
      >
        <Select
          label="Course"
          name="course"
          options={COURSES}
          isRequired
          errorMessage="Choose a course."
        />
        <button type="submit">Save</button>
      </Form>,
    );
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submitted).toBeUndefined();
    expect(screen.getByText("Choose a course.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Course/ }));
    await user.click(screen.getByRole("option", { name: /DNS/ }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submitted?.get("course")).toBe("dns");
  });

  it("shows the selected option with a check mark, not colour alone", async () => {
    const user = userEvent.setup();
    render(<Select label="Course" options={COURSES} defaultValue="gme" />);
    await user.click(screen.getByRole("button", { name: /Course/ }));
    const selected = screen.getByRole("option", { name: /GME/ });
    expect(selected).toHaveAttribute("aria-selected", "true");
    expect(selected.querySelector("svg")).not.toBeNull();
  });
});
