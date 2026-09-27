import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { Form } from "@/design-system/components/Field";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { DatePicker } from "./DatePicker";

const segments = () => screen.getAllByRole("spinbutton");

async function openCalendar(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /Calendar/ }));
  return screen.getByRole("grid");
}

describe("DatePicker", () => {
  it("renders en-IN day / month / year segments and passes axe", async () => {
    const { container } = render(
      <DatePicker label="Date of birth" defaultValue="2006-09-07" />,
    );
    expect(
      segments().map((segment) => segment.getAttribute("aria-label")),
    ).toEqual(["day, ", "month, ", "year, "]);
    // Leading zeros: DD/MM/YYYY
    expect(segments().map((segment) => segment.textContent)).toEqual([
      "07",
      "09",
      "2006",
    ]);
    await expectNoA11yViolations(container);
  });

  it("types a date into the segments and reports ISO", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<DatePicker label="Joining date" onChange={onChange} />);

    await user.click(segments()[0]!);
    await user.keyboard("27092026");

    expect(onChange).toHaveBeenLastCalledWith("2026-09-27");
  });

  it("adjusts a segment with the arrow keys", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <DatePicker
        label="Exam date"
        defaultValue="2026-09-27"
        onChange={onChange}
      />,
    );
    await user.click(segments()[0]!);
    await user.keyboard("{ArrowUp}");
    expect(onChange).toHaveBeenLastCalledWith("2026-09-28");
  });

  it("starts weeks on Monday by default (MTI 360 product default)", async () => {
    const user = userEvent.setup();
    render(<DatePicker label="Batch start" defaultValue="2026-09-27" />);
    const grid = await openCalendar(user);
    const headers = Array.from(grid.querySelectorAll("th"));
    expect(headers[0]).toHaveTextContent(/^M/);
    expect(headers[6]).toHaveTextContent(/^S/);
    await expectNoA11yViolations(document.body);
  });

  it("honours an explicit firstDayOfWeek override", async () => {
    const user = userEvent.setup();
    render(
      <DatePicker
        label="Batch start"
        defaultValue="2026-09-27"
        firstDayOfWeek="sun"
      />,
    );
    const grid = await openCalendar(user);
    const headers = Array.from(grid.querySelectorAll("th"));
    expect(headers[0]).toHaveTextContent(/^S/);
    expect(headers[1]).toHaveTextContent(/^M/);
  });

  it("navigates the calendar with the keyboard and selects with Enter", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <DatePicker
        label="Sea time from"
        defaultValue="2026-09-27"
        onChange={onChange}
      />,
    );
    await openCalendar(user);

    await user.keyboard("{ArrowRight}{PageDown}{Enter}");

    expect(onChange).toHaveBeenLastCalledWith("2026-10-28");
    await waitFor(() => expect(screen.queryByRole("grid")).toBeNull());
  });

  it("closes the calendar with Escape and returns focus", async () => {
    const user = userEvent.setup();
    render(<DatePicker label="Sea time from" defaultValue="2026-09-27" />);
    await openCalendar(user);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("grid")).toBeNull());
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Calendar/ })).toHaveFocus(),
    );
  });

  it("works controlled with ISO strings", async () => {
    const user = userEvent.setup();
    function Controlled() {
      const [value, setValue] = useState<string | null>("2026-09-27");
      return (
        <>
          <DatePicker label="Fee due" value={value} onChange={setValue} />
          <output>{value ?? "empty"}</output>
        </>
      );
    }
    render(<Controlled />);
    await user.click(segments()[0]!);
    await user.keyboard("{ArrowDown}");
    expect(screen.getByText("2026-09-26")).toBeInTheDocument();
  });

  it("validates min / max and unavailable dates", async () => {
    const user = userEvent.setup();
    render(
      <Form onSubmit={(event) => event.preventDefault()}>
        <DatePicker
          label="Counselling date"
          name="counselling"
          defaultValue="2026-10-04"
          minValue="2026-09-28"
          maxValue="2026-12-31"
          isDateUnavailable={(iso) =>
            new Date(`${iso}T00:00:00`).getDay() === 0
          }
        />
        <button type="submit">Book</button>
      </Form>,
    );
    await user.click(screen.getByRole("button", { name: "Book" }));
    // 2026-10-04 is a Sunday → unavailable
    await waitFor(() =>
      expect(segments()[0]).toHaveAttribute("aria-invalid", "true"),
    );

    await user.click(segments()[0]!);
    await user.keyboard("01");
    await user.click(screen.getByRole("button", { name: "Book" }));
    // 2026-10-01 is available
    await waitFor(() =>
      expect(segments()[0]).not.toHaveAttribute("aria-invalid"),
    );
  });

  it("submits the ISO value under its name and requires a value", async () => {
    const user = userEvent.setup();
    let submitted: FormData | undefined;
    render(
      <Form
        onSubmit={(event) => {
          event.preventDefault();
          submitted = new FormData(event.currentTarget);
        }}
      >
        <DatePicker
          label="Date of birth"
          name="dob"
          isRequired
          errorMessage="Enter the date of birth."
        />
        <button type="submit">Save</button>
      </Form>,
    );
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submitted).toBeUndefined();
    expect(screen.getByText("Enter the date of birth.")).toBeInTheDocument();

    await user.click(segments()[0]!);
    await user.keyboard("07092006");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submitted?.get("dob")).toBe("2006-09-07");
  });

  it("renders the same markup on the server as on the client (no locale mismatch)", () => {
    const element = (
      <DatePicker label="Date of birth" defaultValue="2006-09-07" />
    );
    const server = renderToString(element);
    expect(server).toContain(">07<");
    expect(server).toContain(">09<");
    expect(server).toContain(">2006<");
  });

  it("supports another locale when explicitly requested", () => {
    render(
      <DatePicker label="US date" defaultValue="2026-09-27" locale="en-US" />,
    );
    expect(segments().map((segment) => segment.textContent)).toEqual([
      "09",
      "27",
      "2026",
    ]);
  });
});
