import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { Form } from "@/design-system/components/Field";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Textarea } from "./Textarea";

describe("Textarea", () => {
  it("is a labelled multi-line field and passes axe", async () => {
    const { container } = render(
      <Textarea
        label="Counselling notes"
        description="Visible to the admissions team."
      />,
    );
    const textarea = screen.getByRole("textbox", { name: "Counselling notes" });
    expect(textarea.tagName).toBe("TEXTAREA");
    expect(textarea).toHaveAttribute("rows", "4");
    await expectNoA11yViolations(container);
  });

  it("counts characters (uncontrolled) and links the count as a description", async () => {
    const user = userEvent.setup();
    render(<Textarea label="Remarks" maxLength={200} showCount />);
    const textarea = screen.getByRole("textbox", { name: "Remarks" });
    await user.type(textarea, "Sea time pending");
    expect(screen.getByText("16 / 200 characters")).toBeInTheDocument();
    expect(textarea).toHaveAccessibleDescription(
      expect.stringContaining("16 / 200 characters"),
    );
    expect(textarea).toHaveAttribute("maxlength", "200");
  });

  it("counts characters when controlled", async () => {
    const user = userEvent.setup();
    function Controlled() {
      const [value, setValue] = useState("Deck");
      return (
        <Textarea
          label="Summary"
          maxLength={50}
          showCount
          value={value}
          onChange={setValue}
        />
      );
    }
    render(<Controlled />);
    expect(screen.getByText("4 / 50 characters")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Summary" }), " cadet");
    expect(screen.getByText("10 / 50 characters")).toBeInTheDocument();
  });

  it("is required and submits under its name", async () => {
    const user = userEvent.setup();
    let submitted: FormData | undefined;
    render(
      <Form
        onSubmit={(event) => {
          event.preventDefault();
          submitted = new FormData(event.currentTarget);
        }}
      >
        <Textarea
          label="Reason for enquiry"
          name="reason"
          isRequired
          errorMessage="Tell us why."
        />
        <button type="submit">Send</button>
      </Form>,
    );
    const textarea = screen.getByRole("textbox", {
      name: "Reason for enquiry",
    });
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(submitted).toBeUndefined();
    expect(textarea).toHaveFocus();
    expect(screen.getByText("Tell us why.")).toBeInTheDocument();

    await user.type(textarea, "Interested in GME");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(submitted?.get("reason")).toBe("Interested in GME");
  });
});
