import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Form } from "@/design-system/components/Field";
import type { Option } from "@/design-system/components/Select";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Combobox } from "./Combobox";

const PORTS: Option[] = [
  { id: "mum", label: "Mumbai" },
  { id: "che", label: "Chennai" },
  { id: "koc", label: "Kochi" },
  { id: "kol", label: "Kolkata" },
  { id: "vsk", label: "Visakhapatnam" },
];

describe("Combobox", () => {
  it("is a labelled combobox and passes axe", async () => {
    const { container } = render(
      <Combobox label="Home port" options={PORTS} />,
    );
    expect(
      screen.getByRole("combobox", { name: "Home port" }),
    ).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("filters as the user types and selects with the keyboard", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Combobox label="Home port" options={PORTS} onChange={onChange} />);
    const input = screen.getByRole("combobox", { name: "Home port" });

    await user.type(input, "ko");
    const options = within(screen.getByRole("listbox")).getAllByRole("option");
    expect(options.map((option) => option.textContent)).toEqual([
      "Kochi",
      "Kolkata",
    ]);
    expect(input).toHaveAttribute("aria-expanded", "true");
    await expectNoA11yViolations(document.body);

    await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");
    expect(onChange).toHaveBeenLastCalledWith("kol");
    expect(input).toHaveValue("Kolkata");
  });

  it("announces an empty result", async () => {
    const user = userEvent.setup();
    render(
      <Combobox
        label="Home port"
        options={PORTS}
        emptyMessage="No ports match"
      />,
    );
    await user.type(screen.getByRole("combobox"), "xyz");
    expect(
      within(screen.getByRole("listbox")).getByText("No ports match"),
    ).toBeInTheDocument();
  });

  it("closes with Escape", async () => {
    const user = userEvent.setup();
    render(<Combobox label="Home port" options={PORTS} />);
    await user.type(screen.getByRole("combobox"), "m");
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("does not accept custom values by default", async () => {
    const user = userEvent.setup();
    render(<Combobox label="Home port" options={PORTS} defaultValue="che" />);
    const input = screen.getByRole("combobox");
    expect(input).toHaveValue("Chennai");
    await user.type(input, " Port");
    expect(input).toHaveValue("Chennai Port");
    await user.tab();
    expect(input).toHaveValue("Chennai");
  });

  it("supports manual (async-ready) filtering with a loading state", async () => {
    const user = userEvent.setup();
    const onInputChange = vi.fn();
    function Async() {
      const [text, setText] = useState("");
      return (
        <Combobox
          label="Shipping company"
          filtering="manual"
          options={[]}
          isLoading={text.length > 0}
          inputValue={text}
          onInputChange={(next) => {
            onInputChange(next);
            setText(next);
          }}
        />
      );
    }
    render(<Async />);
    await user.type(screen.getByRole("combobox"), "an");
    expect(onInputChange).toHaveBeenLastCalledWith("an");
    expect(screen.getByRole("status")).toHaveTextContent("Loading options…");
    expect(
      within(screen.getByRole("listbox")).getByText("Loading options…"),
    ).toBeInTheDocument();
  });

  it("submits the selected option id under its name and validates required", async () => {
    const user = userEvent.setup();
    let submitted: FormData | undefined;
    render(
      <Form
        onSubmit={(event) => {
          event.preventDefault();
          submitted = new FormData(event.currentTarget);
        }}
      >
        <Combobox
          label="Home port"
          name="port"
          options={PORTS}
          isRequired
          errorMessage="Choose the home port."
        />
        <button type="submit">Save</button>
      </Form>,
    );
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submitted).toBeUndefined();
    expect(screen.getByText("Choose the home port.")).toBeInTheDocument();

    await user.type(screen.getByRole("combobox"), "Kochi");
    await user.keyboard("{ArrowDown}{Enter}");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submitted?.get("port")).toBe("koc");
  });
});
