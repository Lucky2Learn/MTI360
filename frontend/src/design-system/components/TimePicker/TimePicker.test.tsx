import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Form } from "@/design-system/components/Field";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { isoToTime, normalizeLiteral, timeToIso } from "./time";
import { TimePicker } from "./TimePicker";

const segments = () => screen.getAllByRole("spinbutton");

describe("time helpers", () => {
  it("round-trips ISO HH:mm and rejects invalid values", () => {
    expect(timeToIso(isoToTime("09:05")!)).toBe("09:05");
    expect(timeToIso(isoToTime("23:59")!)).toBe("23:59");
    expect(isoToTime(undefined)).toBeUndefined();
    for (const invalid of [null, "", "9:05", "24:00", "12:60", "noon"]) {
      expect(isoToTime(invalid)).toBeNull();
    }
  });

  it("normalises Unicode spaces in literal segments for stable hydration", () => {
    expect(normalizeLiteral("⁩ ⁨")).toBe("⁩ ⁨");
    expect(normalizeLiteral(" ")).toBe(" ");
    expect(normalizeLiteral(":")).toBe(":");
  });
});

describe("TimePicker", () => {
  it("shows en-IN 12-hour segments with leading zeros and passes axe", async () => {
    const { container } = render(
      <TimePicker label="Class starts" defaultValue="14:30" />,
    );
    expect(segments().map((s) => s.textContent)).toEqual(["02", "30", "pm"]);
    await expectNoA11yViolations(container);
  });

  it("types a time and reports ISO HH:mm", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TimePicker label="Class starts" onChange={onChange} />);
    await user.click(segments()[0]!);
    await user.keyboard("0945a");
    expect(onChange).toHaveBeenLastCalledWith("09:45");
  });

  it("adjusts with arrow keys and works controlled", async () => {
    const user = userEvent.setup();
    function Controlled() {
      const [value, setValue] = useState<string | null>("08:00");
      return (
        <>
          <TimePicker label="Muster" value={value} onChange={setValue} />
          <output>{value ?? "empty"}</output>
        </>
      );
    }
    render(<Controlled />);
    await user.click(segments()[1]!);
    await user.keyboard("{ArrowUp}");
    expect(screen.getByText("08:01")).toBeInTheDocument();
  });

  it("supports a 24-hour clock override", () => {
    render(<TimePicker label="Watch" defaultValue="14:30" hourCycle={24} />);
    expect(segments().map((s) => s.textContent)).toEqual(["14", "30"]);
  });

  it("validates min / max and required, and submits with the form", async () => {
    const user = userEvent.setup();
    let submitted: FormData | undefined;
    render(
      <Form
        onSubmit={(event) => {
          event.preventDefault();
          submitted = new FormData(event.currentTarget);
        }}
      >
        <TimePicker
          label="Counselling slot"
          name="slot"
          isRequired
          minValue="09:00"
          maxValue="17:00"
          defaultValue="18:15"
          errorMessage="Choose a time between 9:00 am and 5:00 pm."
        />
        <button type="submit">Book</button>
      </Form>,
    );
    await user.click(screen.getByRole("button", { name: "Book" }));
    expect(submitted).toBeUndefined();
    await waitFor(() =>
      expect(
        screen.getByText("Choose a time between 9:00 am and 5:00 pm."),
      ).toBeInTheDocument(),
    );

    await user.click(segments()[0]!);
    await user.keyboard("{ArrowDown}{ArrowDown}");
    await user.click(screen.getByRole("button", { name: "Book" }));
    expect(submitted?.get("slot")).toBe("16:15:00");
  });

  it("can be disabled", () => {
    render(<TimePicker label="Locked" defaultValue="10:00" isDisabled />);
    segments().forEach((segment) =>
      expect(segment).toHaveAttribute("aria-disabled", "true"),
    );
  });
});
